# Feature Trace 09 — WNS Narrative Pipeline

**Wave:** 2 (parallel with seven content-tool agents)
**Owned endpoints:** `wns_layer2`, `wns_layer3`, `wns_layer4`, `wns_layer5`, `wns_layer6`, `wns_layer7` (six weavers)
**Final output artifacts:** **(a)** the WNS narrative the player reads (journals, world-state panels, daily news) and **(b)** the WNS-to-WES context bundle every WES tool consumes downstream.
**Date:** 2026-05-26

> "The WMS is event marker. The WNS is the story. The WMS is made to list events; the WNS strings them together."
>
> "Ensure that the WES also automatically gets most if not all the context the WNS had."

WNS is the only agent in this pass with two faces. One face points at the player — the chronicle the player encounters as itself, the world's voice describing the world's mood. The other face points at WES — the bundle that every quest, NPC, hostile, material, node, skill, title, and chunk is going to be authored against. Both faces are downstream of the same six weavers; both deserve immaculate plumbing. Slop on either face is a different kind of poison: a bad standalone narrative makes the world feel unwritten; a bad bundle makes every generated artifact feel disconnected from that world.

This trace is structured as **Part A — standalone narrative pipeline** (sections 1-3), **Part B — WNS-to-WES contract** (sections 4-7), **Part C — diversity / speculative** (sections 8-9). Agent 1 already surfaced the single largest cross-tool bug (the `BundleToolSlice` `parent_summaries` leak) — Part B specs the fix from the WNS side.

---

# Part A — The standalone narrative artifact

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

Three places the player encounters WNS as itself:

**(a) The journal / chronicle panel.** The player opens a panel (menu key, designer's call — currently no UI surface exists, see §2.4) and reads a stack of narrative entries. Top of the stack is what their locality is currently saying. Below that, the district's pattern. Below that, the region. Etc. They scroll and the world's voice expands outward: from "the watch in Tarmouth is short three guards this week and the smith's apprentice did not come to the forge" up to "the salt moors are bleeding apprentices toward the docks across three villages this season" up to "the eastern provinces have grown quiet — the silent order's chapter houses haven't reported in a month." Each entry is dated by in-game day; each carries the layer tag (NL2/NL3/...); each is tied to threads the player can click to see prior entries on the same arc. **This is the player reading the world's mind across scales.**

**(b) Event popups at firing time.** When a weaver fires at the locality the player is currently standing in, a brief notification slides up: "*The harbor master's wife took the small boat south and did not come back.*" One line. Dismissable. Click-to-expand for the full fragment. This is the gameplay-current voice — the player learns about the village they're walking through, in the village's own register. Higher-tier firings (NL3, NL4) don't pop up — they're too abstract for that beat. Or do, but quieter and only when severity > threshold (see §8 severity dial).

**(c) Faction event flashes / world-state UI.** Affinity shifts and severity-major NL5+ firings produce world-state banners ("The Karavel succession has entered open phase"). These are inline-with-gameplay flashes the player sees regardless of journal access. The chronicler's voice as the world breathing.

That is the entire experience the standalone narrative pipeline exists to serve. The WMS catalogues what happened; the WNS makes the player feel that the world is paying attention to what happened, that things are accumulating into a story, that history is being written even when the player isn't watching.

### 1.2 Timing budget

Unlike quests (Agent 1's 2-3 second scroll-unfurl mask), WNS narrative is **never on the player's critical path.** A weaving fire that takes 20 seconds doesn't block anything — the journal will just have a slightly older "most recent" entry until the new one lands. This is the entire reason the cascade-by-N architecture works: the player walks around, events accumulate in WMS, every 3 WMS-L2 events at one locality the NL2 weaver fires asynchronously, and the journal gets a new entry whenever it gets one.

Implication: **WNS can afford rich prompts, multiple-pass refinement, and even real-LLM-only inference** (no fixture fallback) in ways the quest tool cannot. The constraint here is not latency but rather not flooding the journal with cheap entries — cascade-by-N is the volume governor.

### 1.3 Failure modes — what BAD looks like

Five flavors. The first three Agent 1 named for quests apply here too; two are WNS-specific.

**(a) Slop.** The narrative is generic. "The village has been busy this week. People come and go." No proper nouns. No causality. Reads like fortune-cookie output. *(Defense: WMS context with real event details, layer-scope rules that demand specificity, the `_layer_scope` fragments naming "BELOW your scope" / "AT your scope" / "ABOVE your scope" with literal examples.)*

**(b) Stagnant predictability.** The same narrative shape every firing. Every NL2 reads "the watch is short three guards." The thread headlines rotate but the prose register doesn't. *(Defense: tone tag variety, tag-indexed assembly so each firing pulls different fragments, the cascading-context delta — last NL2 narrative is in the user prompt so the LLM is explicitly told what NOT to repeat.)*

**(c) Craziness.** The weaver invents an entirely new world. "The dragon-mayor of Goblinburg declared war on bananas." Emergent proper nouns multiply without check; the world becomes incoherent across firings. *(Defense: `emergent_entity` cap of 2 per fragment / 5 per run, the WMS context as factual ground truth the LLM cannot contradict, the cascading parent narrative as a frame the LLM cannot break.)*

**(d) Voice-collapse across layers.** This is WNS-specific. NL2 reads exactly like NL7. The locality chronicler sounds like the chronicler-of-ages; the chronicler-of-ages sounds like the village gossip. The whole point of six layers is six distinct vantage points; if voice collapses, you have one chronicler shouting six times. *(Defense: the `_layer_scope` fragment, the `VOICE:` line in each layer's scope, per-layer `layer:nl<N>` fragments. As of v3.1 the prompts have this — see §8.1.)*

**(e) WMS-WNS voice contamination.** The flip side of (d). WNS leaks into WMS voice ("the player struck three kobolds at the river crossing — but did he hear the moors-stone humming under his feet?") or WMS leaks into WNS voice ("Locality narrative: 12 events fired this week, 7 in domain:combat, 3 in domain:gathering."). Either is fatal — the WMS is the catalog, the WNS is the story, and they must stay separate. *(Defense: the memory `wms_vs_wns_voice_distinction.md`, the `_core.system` rule "treat WMS context as factual ground truth," the user direction "the WMS is event marker, the WNS is the story.")*

### 1.4 What "good" looks like

After an hour of play, the player opens the journal and reads, in the chronicler's voice:

> *"In Tarmouth this week, the watch fell short two guards on the seaward shift and the cliff-school children began drawing the same horned figure across three days running — children draw fashions, but not the same fashion across three days. Three travelers came inland from the moors road; none stayed past one night. The harbor master's wife took the small boat south and did not come back."*

> *(Coast Marches district)* *"Three villages report the cliff-school sign now. The figure crossed locality lines on Tuesday-tide. The watch is short along the coast road — the captain at Tarmouth wrote the captain at Saltreach, asking for two."*

> *(Salt Reach region)* *"The salt moors are restructuring around copper trade. Apprentices are bleeding toward the docks faster than the masters can replace them. The cult-sign the cliff-school children draw matches the rust-mark on the moors-stone — the chronicler at Saltreach claims this for the first time this week."*

Four properties:

- **Specific.** Names places, names people, names actions. Not "the village is troubled."
- **Layered.** Each scope reads differently. The locality talks about names; the district talks about plural villages; the region talks about restructuring.
- **Causally legible across layers.** The player can see how the locality observations promoted into a district pattern that promoted into a regional arc.
- **Continuous.** Threads connect across firings. The cliff-school sign appears at NL2, returns at NL3 next firing, returns at NL4 the firing after.

---

## 2. Output artifact schema completeness audit

WNS does **not have a `NarrativeDefinition.JSON`** the way quests have `QuestDefinition.JSON`. WNS persists to a SQLite database (`world_narrative.db`, sibling of `world_memory.db`), with one row per weaving fire. The row schema lives at `Game-1-modular/world_system/wns/narrative_store.py:36-73` as `NarrativeRow`. The "artifact" is the row plus the threads it materializes.

| Field | Type | Author | Quality bar beyond schema-valid |
|---|---|---|---|
| `id` | str (UUID) | runtime | Server-assigned. |
| `created_at` | float (game time) | runtime | Stamped at weaver fire time, not at LLM-call start. |
| `layer` | int 1-7 | runtime | NL1 is deterministic capture (NL1 ingestor); NL2-NL7 are LLM-authored. |
| `address` | str (e.g. `"locality:tarmouth"`) | runtime | Inherits firing address. |
| `narrative` | str (1-3 sentences) | LLM weaver | **The player-facing prose.** The single most important field. Voice must match `_layer_scope`. May contain inline `<WES>` and `<AffinityShift>` XML which is stripped before persistence. |
| `tags[]` | List[str] | LLM weaver | Content tags from the layer's allow-list. Address tags prepended by runtime; LLM may not emit them. |
| `payload.threads[]` | List[ThreadFragment dict] | LLM weaver + runtime | Headlines + content_tags + relationship. `thread_id` is server-minted; `parent_thread_id` is LLM-supplied (cross-layer promotion link). |
| `payload.call_wes` | bool | runtime (legacy) | True iff `<WES>` directive was parsed out. |
| `payload.directive_hint` | str | runtime (legacy) | First WES call's body. |
| `payload.wes_calls[]` | List[{purpose, body}] | LLM weaver via XML inline | The WES directives the weaver embedded. Body is freeform prose the planner reads. |
| `payload.task` | str | runtime | `"wns_layer<N>"`. |
| `payload.raw_response` | str | runtime | Full LLM output. Kept for observability + debugging. |

Per-layer additions (NL7 only, per `narrative_fragments_nl7.json:15`):

| Field | Type | Author | Notes |
|---|---|---|---|
| `payload.dominant_arcs[]` | List[str] | LLM weaver | World-shaping arcs. NL7-only. |
| `payload.dominant_regions[]` | List[str] | LLM weaver | Region IDs currently in play. |
| `payload.dominant_factions[]` | List[str] | LLM weaver | Faction tags currently in play. |
| `payload.severity` | str enum | LLM weaver | `minor / moderate / significant / major / critical`. Drives world-state UI flash threshold. |

`[FRAGMENT-GAP]` **`severity` is NL7-only in schema, but the journal UI (when built) will want severity at every layer.** A locality firing announcing "the harbor master's wife took the small boat south" needs a severity hint so the popup system knows whether to slide it up or queue it silently. Suggested fix: extend the output schema to include `severity` at every layer with the same enum. Designer-tunable distribution per layer (NL2 should default `mundane`; NL7 should default `minor`).

### 2.1 What's MISSING from the standalone artifact schema

`[WNS-GAP]` **No `display_form` / `chronicle_voice` rendering field.** Today the player would see `row.narrative` raw — including any leftover formatting quirks from the LLM, no prefix denoting layer, no date stamp. The journal UI will want either a stored `display_text` (chronicler-formatted) or a render-time formatter that wraps `[Layer · Address · Day N] {narrative}` consistently. Designer should decide: store-time vs render-time.

`[WNS-GAP]` **No `pinned_quote` / `headline` for the narrative itself.** Threads have headlines, but the narrative row does not. For the journal UI's collapsed view ("Day 47: a list of one-line headlines you click to expand"), the LLM should also emit a one-line headline summarizing the narrative. Suggested addition: `payload.headline` (5-8 words, evocative). Cost: trivial token addition, large UX win.

`[WNS-GAP]` **No `severity` outside NL7.** Already named above.

`[WNS-GAP]` **No `actor_refs` / `entity_refs` extraction.** The narrative names entities ("Captain Vell," "the moors-stone," "the cliff-school children") but doesn't expose them as structured refs. The journal UI cannot link "Captain Vell" in the prose to his NPC sheet. Suggested addition: `payload.entity_refs[]` — list of `{"type": "npc"|"location"|"faction"|"item"|"emergent", "name": "Captain Vell", "registry_id": "moors_copperlash_captain" or null}`. The LLM can extract these as part of its output; cross-ref to registry happens at commit time.

`[WNS-GAP]` **No `read_at` / `read_by_player` flag.** The journal UI's "new entries" indicator needs to know which rows the player has seen. Strict runtime concern — not the LLM's problem — but the schema should reserve a column.

`[WNS-GAP]` **Thread `closure_state` is binary (open/closed via `relationship`) but not lifecycle-aware at the row level.** A thread can be in `inciting_incident` / `rising_action` / ... / `resolution` / `coda` per the `thread_stage:*` tag. But there's no field on the row aggregating "which threads CLOSED this firing" so the journal UI can render closure events specially ("Arc complete: The Salt Reach Hunt has resolved"). Suggested: `payload.threads_closed_this_firing[]` (list of thread_ids that just hit `relationship:close`).

### 2.2 NL1 vs NL2-NL7 schema divergence

NL1 is **not LLM-woven** — it's deterministic capture from NPC dialogue events (per `world_system/wns/nl1_ingestor.py`). NL1 rows are structurally `NarrativeRow` like the woven layers but with `payload.dialogue_text` / `payload.npc_id` / `payload.extracted_mentions` instead of `payload.threads`. The standalone artifact for NL1 is "the NPC said this and the system noticed these mentions" — useful as cascading input to NL2 but NOT presented to the player as journal entry. The journal entry for a locality should aggregate the locality's NL2 narrative WITH the recent NL1 mentions that fed it. UI design surface.

### 2.3 Voice schema by layer (current as of v3.1)

| Layer | Address tier | Voice register | Default thread count | WES purposes typical |
|---|---|---|---|---|
| NL2 (locality) | locality:X | someone walking the streets; concrete physical names | 0-3 | new-npc, new-quest, occasionally new-skill / new-material |
| NL3 (district) | district:Y | pattern-watcher naming villages in plural | 0-3 | new-chunk, new-faction, new-skill, new-npc, new-quest |
| NL4 (region) | region:Z | regional chronicler — biomes, trade, war | 0-3 | new-chunk, new-hostile, new-faction, new-quest |
| NL5 (province) | province:P | provincial historian — governance, faiths, ages | 0-2 | new-faction, new-title |
| NL6 (nation) | nation:R | court historian — dynastic events, treaties | 0-2 | new-title, new-faction |
| NL7 (world) | world:W | chronicler of ages — mood, era, civilizational | 0-1 (default 0) | new-chunk (world-tier biome), new-faction (world-spanning) |

This is the v3.1 furnishing. **Designer has not reviewed.** The current text is scaffold; it's correct in shape but the prose-tier specifics need designer judgement. (Per CLAUDE.md v8.1: "Architecture is now in designer-grindable state — prompt furnishing, balance tuning, fixture enrichment, and N-value playtest runs are the natural next mode.")

### 2.4 The player-facing UI: completely absent

**CRITICAL**: as of the verification scan, there is NO journal panel, NO event popup system, NO world-state UI subscriber to WNS. The `WorldNarrativeSystem` is wired into `core/game_engine.py:4618-4641` and the database fills as the cascade fires, but **nothing presents it to the player.** The "standalone narrative artifact" the player sees today is: nothing. WNS is internal-only.

This is THE primary build item for the standalone deliverable. The trace fields above (§2.1) assume a UI that doesn't exist yet. Adding the schema fields without the UI is half the work. Adding the UI without the schema fields is the other half. Both are required.

`[WNS-GAP]` **Journal/chronicle UI not built.** The biggest single piece of "user-facing standalone narrative" infrastructure missing. Suggested home: `core/game_engine.py` event-handler hook + a new `rendering/journal_panel.py` reading from `WorldNarrativeSystem.store.query_recent_by_layer(...)` and rendering chronicler-formatted entries.

`[WNS-GAP]` **Event popup system for locality firings not built.** Smaller scope than full journal UI — a notification slide for "the locality you're standing in just had a firing" requires (i) a subscriber to `WNS_FIRED` (currently fired only into observability buffer at `nl_weaver.py:759`, not the bus), (ii) a notification widget in `rendering/`, (iii) severity-based filter logic.

`[WNS-GAP]` **`WNS_FIRED` event not published on the bus.** Today `obs_record(EVT_WNS_FIRED, ...)` only writes to the ring buffer for the F12 observability overlay. The journal UI (when built) needs a real GameEventBus publish so the panel can refresh and the popup widget can listen. Suggested: publish `WNS_NARRATIVE_FIRED` on the bus with the row id; subscribers fetch the row from the store.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a competent 1990s systematic generator (no LLM) produces, given a WMS event count per locality:

```
[Day 47 · Locality: Tarmouth]
This week: 5 enemies killed (kobold_grunt, kobold_archer), 2 materials gathered (iron_ore, oak_log), 1 NPC interaction (village_elder_01).

[Day 47 · District: Coast Marches]
This week, 3 localities reported activity. Total events: 18. Most common domain: combat.

[Day 47 · Region: Salt Reach]
This week, 4 districts reported activity. Total events: 47. Most common domain: combat.
```

This is fine. This is also stat-readout, not story. The player learns nothing they couldn't get from the WMS daily ledger directly. There is no THREAD; there is no INTERPRETATION; there is no VOICE. After three sessions the player stops opening the journal.

### 3.2 What the LLM weaver has to add

Field-by-field, what the LLM must contribute that the slot machine can't:

1. **Voice register.** Locality-vs-region-vs-world voice is the whole point. The slot machine has one voice (telegraph-style readout). The LLM has six.
2. **Interpretation.** "The watch is short three guards" + "the smith's apprentice did not come to the forge" + "three travelers arrived inland" are three WMS events. The LLM connects them: "the village is bleeding people inland this week." Slot machine cannot do this.
3. **Thread continuity.** A NL2 thread "watch undermanned for the season" opened at firing 1; the LLM at firing 2 continues it ("the watch is now short FIVE guards — the season is biting earlier than last year"). Slot machine treats every firing as independent.
4. **Cross-layer promotion.** NL2 emits threads with `parent_thread_id=null`; NL3 reads those threads as `lower_primary_threads` and promotes them ("three villages now report the watch shortage — this is a coastal pattern, not a Tarmouth quirk"). Slot machine cannot aggregate.
5. **WES directive synthesis.** When a pattern wants new content ("the cult-sign the children draw matches the rust-mark on the moors-stone — this implies a new faction"), the LLM embeds `<WES purpose="new-faction">...</WES>`. Slot machine cannot author content requests because it doesn't know what content would fit.
6. **Affinity shift detection.** When a narrative implies a faction's standing has shifted ("the moors raiders are quiet — none of their riders have come down the coast road in two weeks"), the LLM embeds `<AffinityShift>` directives. Slot machine cannot make this judgment.
7. **Tone modulation.** Same factual event base → different tones (`tone:grim` vs `tone:hopeful`) based on thread state + cascading parent narrative. Slot machine produces one tone (neutral).
8. **Emergent proper nouns.** The chronicler can coin "the Moors-Stone Massacre" if patterns warrant. Slot machine cannot.

The delta is **voice, interpretation, continuity, and contribution to the content pipeline.** Slop is unavoidable if the LLM is given thin context; quality is achievable if the LLM is given rich cascading context plus tag-indexed prompt fragments. The architecture supports the latter; designer prose review is the bottleneck.

---

# Part B — The WNS-to-WES contract

This is the half the eight content-tool agents are waiting on. Every Wave 2 agent will ask "what does WNS give me when my tool fires?" The contract below is the authoritative answer.

## 4. Backward trace from WES tool needs

The WES pipeline downstream of a `<WES purpose="...">` emission goes:

```
NL weaver emits <WES> → build_wes_bundle() → WNS_CALL_WES_REQUESTED event →
WESOrchestrator → LLMExecutionPlanner.plan(bundle) →
WESPlan with steps[] → PlanDispatcher → for each step:
  slice_bundle_for_tool(bundle, tool_name) → BundleToolSlice →
  LLMExecutionHub.build_specs(step, slice) → ExecutorSpec[] →
  LLMExecutorTool.run(spec) → content artifact
```

Each of the 8 content tools (chunks, npcs, hostiles, materials, nodes, skills, titles, quests) reads from a `BundleToolSlice` derived from the WESContextBundle the WNS emitted. **The contract is what the slice carries forward, what it strips, and what the tool can rely on.**

### 4.1 What every content tool needs from WNS (generally)

Reading across Agent 1's quest trace and projecting to the other seven:

- **The directive body** (`<WES purpose="...">BODY</WES>`). The LLM-authored prose framing why this content is being asked for. Already in `BundleToolSlice.directive_text`.
- **The firing address.** Where in the world is this content for. Already in `BundleToolSlice.address_hint`.
- **The firing tier.** Drives scope discipline at the tool layer (a chunk co-emitted from an NL2 fire should be locality-flavored; from an NL5 fire, kingdom-flavored). Already in `BundleToolSlice.firing_tier`.
- **The threads at the firing address.** What arcs is this content born into. Already in `BundleToolSlice.threads_in_focal_address` — but only those at the focal address, parent-address threads are dropped.
- **The PARENT narrative the firing cascaded from.** "What does the district / region / nation arc say about this?" This is the **`parent_summaries` field on the bundle, currently STRIPPED at slice time.** Single largest gap.
- **The firing-layer narrative the WNS just wrote.** "What does this locality just say about itself?" This is the **`firing_layer_summary`** — same situation, only the planner sees it (via `_bundle_to_vars`), not the hub or tool.
- **Recent registry entries of the same tool's type.** Diversity guard — don't author the 12th identical herb gather quest. Already in `BundleToolSlice.recent_registry_entries` (caller-supplied).
- **The geographic chain.** Names and biomes from locality up to world. Currently in `bundle.directive.scope_hint` but the planner doesn't surface it to the tool slice.
- **Co-emitted artifacts in the same plan.** When `quests` depends on `npcs` co-emitted in the same plan, the quest hub should see the NPC's spec / draft. Currently the dispatcher passes a `step_slots` reference but not the actual artifact data.
- **WMS factual context.** What raw events fed this firing. The bundle has `delta.wms_events_since_last[]` (currently empty — see §5) and `delta.npc_dialogue_since_last[]` (also empty).

### 4.2 What CONTENT-TYPE-SPECIFIC needs add to the general list

(I haven't seen the other seven Wave 2 traces yet — they're running in parallel. Anticipated needs, drawn from the working doc + ledger + my own read of the code.)

- **Chunks tool**: needs `geographic_chain` to know biome lineage (a "rust moors" chunk in a "coastal" region wants rusted cliffs; same chunk type in a "highland" region wants different texture). Also needs lower-layer narrative — what do localities in this district say about the new chunk? *(Suggests `scope_hint.geographic_chain` must reach the chunk hub.)*
- **NPCs tool**: needs the giver's narrative seed — the prose-fragment that named or implied this NPC. Today this reaches the tool via `flavor_hints.prose_fragment` (the hub picks it from the directive). But the NPC's PERSONALITY tag (the speechbank archetype) wants the cascading TONE tag from the thread — `tone:grim` threads want grim NPCs, `tone:hopeful` threads want hopeful NPCs. **The tool needs the thread's content_tags, not just its headline.** Today `BundleToolSlice.threads_in_focal_address` carries full `ThreadFragment` (with content_tags), but the hub's `_make_vars` only extracts `[t.headline for t in slice.threads_in_focal_address]` — tags get dropped at the hub→tool boundary. **Same leak shape as parent_summaries.**
- **Hostiles tool**: needs the WMS context — what enemies have the player been fighting recently? A new hostile born from a "the moors raiders are sending stronger riders" thread should match the raiders' tag family, not invent a new one. WMS events delta is the carrier. Today empty.
- **Materials / Nodes tool**: needs the geographic chain (biome → material plausibility) AND the WMS context (what materials are being gathered recently, to avoid duplication or to lean into shortages).
- **Skills / Titles tool**: needs the cross-feature co-emission visibility — a skill being granted as a quest reward needs to know what the quest's tier and theme are. Today co-emission visibility is half-built (the dispatcher knows about it but doesn't pass artifacts forward).
- **Quests tool**: needs everything. The most context-hungry tool. Agent 1's trace is the canonical reference.

### 4.3 The pattern

**Every content tool wants more than `BundleToolSlice` currently carries.** The slice was designed parsimoniously ("hubs don't need the wide view, just the focused view") but the parsimony is too aggressive — narrative context, parent summaries, cross-layer threads, geo chain, and WMS events delta are all surgically removed at the slice boundary and the tools have no way to reach back.

The fix is not "give the tool the full bundle" — that's too much context for compact prompts. The fix is **extend `BundleToolSlice` to carry the load-bearing context, AND have the hub/tool prompts explicitly consume it.** §5 lays out the per-field provenance.

---

## 5. Per-bundle-field provenance table

This is the contract. For each field in the bundle, where it comes from, what currently happens, and what needs to change. **The eight content-tool agents should treat this as authoritative.**

| Bundle field | Source (WNS-side) | Currently passed to WES tool? | Where stripped | What needs to change |
|---|---|---|---|---|
| `bundle_id` | `build_wes_bundle()` `nl_weaver.py:680` | Yes (slice copies it) | — | — |
| `created_at` | game time at weaver fire | No (slice drops) | `slice_bundle_for_tool` `context_bundle.py:342-370` | Probably fine to drop; tool doesn't need timestamp. |
| `delta.address` | `weaver_ctx.address` | Yes as `address_hint` | — | — |
| `delta.layer` | `weaver_ctx.layer` | Yes as `firing_tier` | — | — |
| `delta.start_time` / `end_time` | game_time | No | Slice drops | OK — temporal context isn't critical for tools. |
| `delta.npc_dialogue_since_last[]` | **EMPTY** by builder | No | Builder doesn't populate (`wns_to_wes_bridge.py:148-152`) | `[WNS-GAP]` — bridge should query NL1 store for dialogue since previous fire at this address and populate. NPC tool wants this. |
| `delta.wms_events_since_last[]` | **EMPTY** by builder | No | Builder doesn't populate | `[WNS-GAP]` — bridge should pull from `event_store` (the bridge already has access via `wms_facade`). Hostiles, Materials, Nodes tools want this. |
| `narrative_context.firing_layer_summary` | `just_written_narrative` (the narrative the weaver just wrote) | **PLANNER ONLY** (via `_bundle_to_vars`) | `slice_bundle_for_tool` line 359-370 | `[WES-SCHEMA-GAP]` — extend `BundleToolSlice` with `firing_layer_summary` field. Hub `_make_vars` exposes it as `${firing_narrative}` template variable. |
| `narrative_context.parent_summaries{}` | `_build_parent_summaries(weaver_ctx)` `wns_to_wes_bridge.py:69-96` | **NOBODY** sees this — not planner, not hub, not tool | Planner `_bundle_to_vars:172-181` only reads `firing_layer_summary`; slice ignores entirely | `[WES-SCHEMA-GAP]` **THE BIG ONE.** Extend `BundleToolSlice` with `parent_summaries: Dict[str, str]`. Extend planner `_bundle_to_vars` to include `bundle_parent_summaries`. Extend hub `_make_vars` to expose `${parent_narratives}`. Single fix; all 8 tools win. |
| `narrative_context.open_threads[]` (full `ThreadFragment` list) | `_trim_threads(weaver_ctx.self_active_threads)` | Partially — slice copies the focal-address subset, hub extracts only `headlines` | Hub `_make_vars:179-181` does `[t.headline for t in slice.threads_in_focal_address]` — drops content_tags + relationship + parent_thread_id | `[WES-SCHEMA-GAP]` — hub should expose `${thread_fragments}` as full structured data (headline + content_tags + relationship), not just `${thread_headlines}`. NPC, Hostile tools want the tags. |
| `narrative_context.open_threads[]` AT PARENT ADDRESSES | **NOT INCLUDED** in bundle | N/A — never carried | Bridge builder doesn't fetch parent-address threads | `[WNS-GAP]` — bridge should call `extract_active_threads` at `above_primary_address` (and above_fading_address) and include them in `open_threads`. Today only same-layer/same-address threads survive. |
| `directive.directive_text` | `wes_call.body` | Yes | — | — |
| `directive.firing_tier` | `_layer_to_firing_tier(layer)` | Yes | — | — |
| `directive.scope_hint.firing_address` | Bridge | Reaches planner (in user template) | — | — |
| `directive.scope_hint.geographic_descriptor` | `geo_ctx.rendered` | Planner reads via scope_hint but the planner user_template doesn't expose `${geographic_descriptor}` | Planner prompt doesn't unwrap scope_hint sub-fields | `[FRAGMENT-GAP]` — planner prompt fragment needs `${geographic_descriptor}` and `${geographic_chain}` slots in the user template. |
| `directive.scope_hint.geographic_chain[]` | `geo_ctx.tier_briefs` | Reaches planner via scope_hint dict but is dropped at slice | Slice doesn't propagate scope_hint at all | `[WES-SCHEMA-GAP]` — extend `BundleToolSlice` with `geographic_chain: List[Dict]`. Chunks tool needs this most acutely. |
| `directive.scope_hint.weaver_layer` | `layer` | Same as firing_tier | — | — |
| `directive.scope_hint.purpose` | `wes_call.purpose` | Yes — reaches planner | — | — |
| `source_narrative_layer_ids[]` | `[source_row_id]` | No — slice drops | Slice drops | Probably fine; debug-only provenance. |

### 5.1 The single highest-leverage fix

Five lines in `context_bundle.py:slice_bundle_for_tool` plus five lines each in `LLMExecutionPlanner._bundle_to_vars` and `LLMExecutionHub._make_vars`, plus three template-variable additions to the planner + each hub's prompt fragment file. Touches `parent_summaries`, `firing_layer_summary`, `geographic_chain`, and the structured thread payload. **One PR fixes the disconnected-from-WNS-narrative failure mode for all 8 content tools.**

Sketch of the new `BundleToolSlice`:

```python
@dataclass
class BundleToolSlice:
    tool_name: str
    bundle_id: str
    firing_tier: int
    directive_text: str
    address_hint: str
    # NEW — narrative context propagation
    firing_layer_summary: str = ""               # what the weaver JUST wrote
    parent_summaries: Dict[str, str] = field(default_factory=dict)  # what the cascading parents say
    # NEW — geographic chain so tools can read biome / region lineage
    geographic_chain: List[Dict[str, Any]] = field(default_factory=list)
    # EXISTING — thread fragments at focal address (full payload, not just headlines)
    threads_in_focal_address: List[ThreadFragment] = field(default_factory=list)
    # NEW — thread fragments at PARENT addresses (so locality content sees district-arc context)
    threads_in_parent_addresses: List[ThreadFragment] = field(default_factory=list)
    # NEW — WMS factual context delta (for tools wanting world-state read)
    wms_events_since_last: List[WMSLayerRow] = field(default_factory=list)
    # EXISTING — diversity guard
    recent_registry_entries: List[Dict[str, Any]] = field(default_factory=list)
```

And the hub's `_make_vars` extends to:

```python
return {
    "tool_name": self.name,
    "plan_step_id": step.step_id,
    "step_intent": step.intent,
    "step_slots": step.slots,
    "directive_text": slice.directive_text,
    "address_hint": slice.address_hint,
    "firing_tier": slice.firing_tier,
    # NEW
    "firing_narrative": slice.firing_layer_summary,
    "parent_narratives": "\n".join(
        f"[{key}] {summary}" for key, summary in slice.parent_summaries.items()
    ),
    "geographic_chain": slice.geographic_chain,
    "wms_events_summary": _render_wms_brief(slice.wms_events_since_last),
    # CHANGED — expose full thread payloads, not just headlines
    "thread_fragments": [t.to_dict() for t in slice.threads_in_focal_address],
    "parent_thread_fragments": [t.to_dict() for t in slice.threads_in_parent_addresses],
    # EXISTING
    "recent_registry_entries": slice.recent_registry_entries,
}
```

Hub prompt fragments add the new template variables; planner prompt fragment adds the new variables too. **Roughly 20-30 lines of code change + designer prose review for the planner's + each hub's user_template.**

### 5.2 What WAS the slice for, originally?

The doc comment on `slice_bundle_for_tool` says: *"Hub does NOT get the full delta (irrelevant to a shape-filler) or parent-address summaries (only the planner needs the wide view)."* This reflects the v3 design where the hub was a thin shape-filler. The v4 design — where tools want narrative continuity, voice anchors, and cross-layer awareness — has outgrown that design. **The contract needs to evolve. This trace is the formal proposal.**

### 5.3 The 9-rung WMS-extraction walk — applied to "what does WNS need to carry?"

User direction: *"be stringent on any WMS gaps and do not allow the agents to use it as a way to escape problem solving."*

I walked the 9 rungs for one tempting `[WMS-GAP]`: **player-encountered-content history at this address.** The use case: when a NL2 weaver fires at a locality the player has been to dozens of times, the narrative should reflect "the player knows this place" subtly (named NPCs of theirs, paths they've worn). When at a locality the player has never been to, the narrative should be untouched-by-player.

1. **Direct query**: WMS event `player_visit` exists per `event_store`? Yes, in `wms_events_chunk_explored` evaluator. **Pass.**
2. **Adjacent events**: visit count per locality from `social.player_visits.count` ledger row — already aggregated.
3. **Negative patterns**: "player NEVER visited" detectable as absence.
4. **Aggregation**: `daily_ledger.player_visits_by_locality` (suggested if not present — see audit).
5. **Trajectory**: visit recency curve — recent vs distant.
6. **Cross-layer climb**: NL3+ narratives carry "the player has been here this week" tone tags.
7. **Cross-entity composition**: player visits + player NPC interactions + player faction affinity = "player has invested in this place."
8. **Stat / ledger lookup**: `StatTracker.locations_explored_count` + `FactionSystem.local_affinity` = ready.
9. **Trigger history**: `WMS_INTERPRETATION_CREATED` with player-action tags filtered by address.

**Verdict**: NOT a WMS gap. The signal exists in WMS — it's just not in the bundle. Tag the bridge to enrich the bundle with `player_familiarity_signal: {visits: N, recent: bool, affinity_band: str}` for the firing address. Marker: `[WNS-GAP]` on the bridge's bundle assembly, NOT `[WMS-GAP]`. Consistent with Agent 1's verdict.

**Zero `[WMS-GAP]` markers in this trace.** WMS substrate is solid; every interesting context fact is reachable. The gaps are all on the WNS-side of the boundary — bridge assembly thinness, slice leakage, and prompt-template variable omissions.

---

## 6. Cross-references with other features (personal shopper for the 8 content tools)

WNS serves all of them. The cross-cutting concerns split into "things every tool needs and WNS provides once" vs "things specific tools need that WNS must vary per tool."

### 6.1 Shared substrate WNS provides once (consumed by all 8)

- **The bundle itself.** One `WESContextBundle` per `<WES>` directive, sliced per tool. The slice contract above is the single point of leverage for all 8.
- **The directive_text.** Every hub prompt has `${directive_text}` and reads from `BundleToolSlice.directive_text`. Consistent.
- **The firing_tier scope rules.** Planner alone reads firing_tier and decides which tools fire; consistent across tools.
- **`recent_registry_entries`.** Currently caller-supplied; needs orchestrator-layer wiring (see Agent 1 §4.5). Same fix benefits all hubs.

### 6.2 Per-tool variance WNS must provide

| Tool | Specific WNS need | Bundle field that carries it (post-fix) |
|---|---|---|
| Chunks | Biome lineage, region/nation tone | `geographic_chain[]`, `parent_summaries` for region+ |
| NPCs | Tone of birth-thread + cascading faction context | `threads_in_focal_address[].content_tags`, parent affinity context |
| Hostiles | What enemies have been around recently + region biome | `wms_events_since_last[]` filtered to combat, `geographic_chain` |
| Materials | Recent gathering activity + biome plausibility | `wms_events_since_last[]` filtered to gathering, `geographic_chain` |
| Nodes | Same as materials | Same |
| Skills | Cross-feature co-emission (which NPCs teach this), thread theme | Co-emission propagation (Agent 1 §4.5), `threads_in_focal_address[].content_tags` |
| Titles | Cross-feature co-emission (which quest grants this), severity context | Co-emission propagation, `severity` (new field, §2.1) |
| Quests | Everything. The most context-hungry. | All of the above. |

**Implication for the 8 content-tool agents**: when you write your trace and say "WNS doesn't give me X," check this table first. If X is in the post-fix bundle, your gap is `[WES-SCHEMA-GAP]` (the slice doesn't carry it) and the fix is here. If X is NOT in the post-fix bundle, your gap is `[WNS-GAP]` against me, and I need to expand the bundle.

### 6.3 Recommendations FROM the WNS to the 8 content-tool agents

- **Don't accept "the bundle doesn't carry it" as a final answer.** Push back. The bundle's job is to carry what tools need.
- **DO accept the per-purpose firing guidance gap.** Agent 1 named this for `new-quest`; it's true for all 8 purposes. The `_wes_tool` body in each NLn fragment file gives generic guidance per layer but not per purpose. Cross-tool design decision: should the firing guidance be **per-purpose-per-layer** (more prompt mass, sharper guidance) or **per-purpose** at the planner layer (less mass, single point of guidance)? Recommend: per-purpose-per-layer, because the same purpose at NL2 vs NL4 wants very different framings. Per-purpose-per-layer means **48 new fragment blocks across the 6 NL files** — designer work.
- **DO accept that the `_wes_tool` body in `narrative_fragments_nl<N>.json` is the place to influence what your tool sees.** It's the weaver's instruction for "when to fire your purpose, what to put in the body, what flavor to lean into." Agent 1 named this for `new-quest`; every other agent should specify their purpose's firing guidance for me to integrate.
- **DO accept that the bundle's bandwidth is bounded.** Token budget on LLM prompts is real. The slice's parsimony was right in intention even if too aggressive in execution. Help me decide what NOT to carry too.

### 6.4 Cross-feature consistency the WNS enforces

- **Tag library discipline.** WNS narratives use tags from the WMS shared library (via `_load_wms_fragments`) plus the WNS-only tags (`thread_stage:*`, `tone:*`, `relationship:*`, etc.). The 8 content tools should draw from the SAME library (the WMS one, augmented per memory `tag_system_functionality.md`). If a tool wants a new tag, it gets a `NEW:` prefix; the consolidation phase (Wave 3) reviews them.
- **Voice consistency at parent narrative.** When a quest tool authors `description_full.narrative` referencing the district arc, the prose should rhyme with the WNS NL3 narrative at that district. The way to make this happen is the bundle slice fix: tools see the parent narrative; their prompts say "be consistent with parent narrative voice."
- **Emergent proper noun propagation.** When NL3 coins "the Moors-Stone Massacre" as a thread arc_hint, quests/chunks/NPCs co-emitted in the same plan can reference it. The arc_hints are in `ThreadFragment.headline` — they reach tools if the slice carries thread payloads (post-fix).

---

## 7. Storage / timing design

### 7.1 Bundle assembly cadence

One `WESContextBundle` per `<WES>` directive parsed out of a weaver narrative. The weaver may emit 0-2 `<WES>` calls per run (hard cap per `wes_call_parser.py:DEFAULT_MAX_CALLS_PER_RUN`). Each spawns one bundle, one `WNS_CALL_WES_REQUESTED` event, one orchestrator plan.

**Multi-directive case**: when one weaver fires emits `<WES purpose="new-chunk">` AND `<WES purpose="new-faction">`, two SEPARATE bundles get built — each one carries the FULL state at firing time, but each gets its own `directive_text` and `purpose`. The two plans run independently downstream. This is fine *(no shared-bundle optimization needed)* because the bundle is small (mostly small strings) and serialization is fast.

`[WNS-GAP]` **Cross-directive deduplication**: if two purposes from the same weaving want overlapping content (e.g. `new-faction` and `new-npc` both implying the same NPC's faction), there's no dedup. The orphan-resolver detects this LATER (the second tool sees the first tool's commit). Suggested: at bundle-pair build time, group multi-directive emissions into a single bundle with a `directives[]` list (multiple WNSDirective entries) and let the planner author one plan covering all. Designer call; deferred until multi-directive examples accumulate.

### 7.2 Slice-per-tool

`slice_bundle_for_tool(bundle, tool_name, recent_registry_entries)` is the deterministic projection. Today it strips too aggressively (see §5). Post-fix, the slice carries narrative context but still per-tool-customized (a chunks tool slice might include biome-emphasis hint that the npcs tool slice doesn't, etc.).

Suggestion: **slice fan-out** — the dispatcher calls `slice_bundle_for_tool` ONCE per plan step, caches the slice, hands it to the hub, hub fans out to N tool invocations on the same slice. Same slice for all specs from one plan step. Already the architecture; just naming the invariant.

### 7.3 Thread continuity — where state lives

Thread state is **NOT in the bundle**. It's in the WNS store (`narrative_store.py`). The weaver pulls active threads via `extract_active_threads(rows)` (`cascading_context.py:99-136`) and includes them in the bundle's `open_threads[]`. When a downstream tool wants to know "what's the current state of this arc?" they read the open_threads payload.

This is correct architecture. Thread state lives WHERE THREADS LIVE (the narrative store). The bundle is a snapshot. Downstream tools cannot mutate thread state — only the next weaving fire updates it via `relationship: continue/reframe/close`.

`[WNS-GAP]` **Thread-aware archive query.** When a quest tool authors a quest under `wns_thread_id`, the quest archive (when built per Agent 1 §7.5) should be queryable from the next WNS fire — "show me archived quests under thread_id X, that's the player's track record on this arc." Today no API exists for this. The fix is the archive table itself plus a `WorldQuery.archived_quests_by_thread(thread_id)` method readable by WMS context builder. Cross-feature work; flagged for consolidation.

### 7.4 Bundle persistence

Bundles serialize to JSON via `to_dict()`. Per the working doc, they're logged next to plan logs as `bundle.json`. **For observability and replay.** No retention strategy is currently specified; old bundles accumulate forever.

`[WNS-GAP]` **Bundle log retention policy.** Suggested: retain last N bundles per address-tier, or last N hours of bundles, configurable. Tiny implementation cost; matters for save bloat in long playthroughs.

### 7.5 NL1 ingestion → NL2 cascade timing

NL1 captures NPC dialogue deterministically (`nl1_ingestor.py`). The NL2 cascade counter increments on WMS L2 events, not on NL1 events. **NL1 rows do NOT trigger NL2 fires directly.** They're cascading INPUT to NL2 when NL2 fires for other reasons.

This is correct in principle but the bundle delta is supposed to carry `npc_dialogue_since_last[]` — and that field is empty today (`wns_to_wes_bridge.py:148-152` constructs an empty NarrativeDelta). For NPC tool firings, dialogue history is the single most useful WNS-side signal — what has the locality's existing NPCs been saying recently? Strictly: this is a builder gap. **Fix**: bridge queries NL1 store for `npc_dialogue` rows since `weaver_ctx.previous_fire_time` at this address, populates `delta.npc_dialogue_since_last[]`.

---

# Part C — Diversity and speculative

## 8. Diversity / creativity design

### 8.1 Voice per layer — the prime diversity dial

Six voices: village-gossip-with-names → pattern-watcher → regional-chronicler → provincial-historian → court-historian → chronicler-of-ages. Each one's `_layer_scope` fragment defines BELOW / AT / ABOVE plus a one-line `VOICE:` declaration. The v3.1 prompts have this; **designer hasn't reviewed.** This is the load-bearing prose for the standalone-narrative quality delta.

Designer task: read each `_layer_scope` and ask "does this voice sound distinct from the layer below and above?" If the locality voice and the district voice both read like "an observer noting events," collapse failure mode (1.3.d) is in play. Examples in the fragment file are the surface area to tune.

### 8.2 Thread continuity — the second-order diversity dial

A thread that opens at NL2 firing 1, continues at NL2 firing 2, gets promoted to NL3 firing 1, continues at NL3 firing 2 — that's **6 narrative events on one arc, each one slightly different.** The diversity is in how the arc EVOLVES across firings: stage progression (`inciting_incident` → `rising_action` → `complication` → ...), tone evolution, scope promotion.

Diversity collapse failure: every firing opens a new thread with `relationship:open`. No continuity. The world reads as a series of disconnected events. *(Defense: the `relationship` field allow-list, the `thread_index` matching logic, the cascading context exposing prior threads.)*

Diversity over-rotation failure: every firing emits `relationship:continue` for some existing thread. No NEW threads ever open. The world reads as the same story repeating. *(Defense: the prompt's "0-3 fragments, default 0 if locality is flat" guidance, the `thread_stage:resolution` / `coda` exits that close arcs.)*

The right ratio is designer-tuned in playtest. Suggested starting distribution per firing:
- 40% continue / reframe existing threads
- 30% open new threads
- 20% close existing threads (`relationship:close`)
- 10% no thread emission (locality is flat this week)

### 8.3 Tag-indexed prompt assembly health

The v3.1 prompts (per `feedback_wns_prompts_must_be_tag_indexed.md`) are tag-indexed. `_collect_firing_tags` (`nl_weaver.py:229-256`) gathers `layer:nl<N>` + content_tags from active threads + content_tags from lower-primary threads. `_build_system_prompt` (lines 258-339) assembles in order: core.system → game_context (from WMS file) → layer_scope → per-tag fragments (WMS factual + WNS narrative-lens) → wes_tool → affinity_shift_tool (NL3+) → output.

Health check:
- **WMS fragments reused?** Yes — `_load_wms_fragments` pulls from `world_system/config/prompt_fragments.json` and the assembler emits both factual and narrative-lens fragments for the same tag. Good.
- **WNS-only tags present?** Yes — `thread_stage:*`, `tone:*`, `relationship:*`, `agency:*`, `narrative_domain:*` live only in the WNS file. Good.
- **Coverage?** The WNS files cover 10 tones × 10 relationships × 7 thread_stages × 10 narrative_domains × 5 agencies + tier:1-4 + rank:* + domain:*. About 50-60 fragments per file. **Designer review surface.** v3.1 prose is scaffold.

`[FRAGMENT-GAP]` **Per-purpose firing guidance.** The `_wes_tool` body in each NLn file gives generic guidance like "common purposes at this scope: new-chunk, new-faction, new-skill." It does NOT say "for `new-quest`, name the giver + name the target + name the grievance." Per-purpose-per-layer expansion needed — 48 new fragments across 6 files (~6 purposes × 6 layers, with most layers using ~3-5 typical purposes). Heavy designer work; high payoff.

`[FRAGMENT-GAP]` **Per-purpose body shape.** Same dimension. The directive_text body shape matters as much as when-to-fire. "new-faction" body should say "name the faction's defining grievance + their geographic scope + their tier (1-4) + whether they're hostile/neutral/friendly." Today the prompt says "1-2 sentences" and trusts the LLM.

### 8.4 WMS context budget (per layer)

`build_wms_brief` defaults to 600 chars (`wms_context_builder.py:34`). At NL2 this is rich (a half-dozen interpretations). At NL7 this is sparse (a few aggregated chronicler lines). **Designer-tunable per layer** via `narrative-config.json:wms.char_budget_by_layer.NL<N>`. Today single global default; should vary.

### 8.5 Emergent entity caps

Hard cap per `narrative_fragments_nl<N>.json:emergent_entity` — 2 per fragment, 5 per run. This is THE designer review surface for unrepeatability. Every emergent proper noun is one-off. **Maintenance burden**: when the LLM coins "the Moors-Stone Massacre," subsequent runs should reference it (continuity) but new runs at other localities shouldn't accidentally re-coin the same name (unintentional re-use). Today no dedup mechanism exists; relies on cascading context exposing the name to future runs. Playtest will tell.

### 8.6 Severity dial

Currently NL7-only (per §2.1). Adding it to every layer enables UI / popup filtering. Suggested layer defaults:

| Layer | Default severity | When to escalate |
|---|---|---|
| NL2 | mundane | tier:3-4 event + boss/unique rank → moderate; cataclysmic locality event → major |
| NL3 | mundane | cross-locality pattern → moderate; district-defining → significant |
| NL4 | moderate | regional-scope shift → significant; war/cataclysm → major |
| NL5 | moderate | provincial → significant; war / succession → major |
| NL6 | significant | nation-defining → major; civilizational stake → critical |
| NL7 | minor | civilizational → major; age-ending → critical |

UI popups gate on severity ≥ moderate at locality, ≥ significant at district, etc.

---

## 9. Speculative future endpoints

### 9.1 `wns_thread_summarizer` — chronicler-voice arc summary

When a thread closes (`relationship:close`), the weaver could optionally emit a 1-2 sentence retrospective ("The watch shortage that began in early spring closed this week — the harbor master's wife returned with three boats and the captain at Tarmouth wrote his thanks to the captain at Saltreach"). Stored as a special `thread_closure` row in the WNS store. **Fuel for journal UI "completed arcs" panel.**

- **Trigger**: weaver emits a thread with `relationship:close`; runtime fires a follow-up LLM call.
- **Inputs**: the closing thread's full history (all fragments under this thread_id across firings).
- **Outputs**: 1-2 sentence retrospective + tags.
- **Latency budget**: not player-facing; async.
- **Cost**: roughly half of a normal weaver fire (smaller context).

`[WNS-GAP]` candidate — design-only, not implemented. Useful but premature.

### 9.2 `wns_player_facing_summarizer` — journal entry formatter

The raw weaver output is "voice + threads + tags." The journal UI may want a slightly different format — leading headline + body + linked entities. An optional render-time LLM pass could format raw narrative into journal-ready prose with consistent formatting. **Probably overkill** — render-time formatting can be deterministic (string templates), not LLM. Flagged for completeness.

### 9.3 Multi-directive bundle compression

Per §7.1, today multi-directive emissions produce N separate bundles. A future optimization: one bundle with a `directives[]` list. Planner sees all directives, authors ONE plan covering all. Reduces redundant context propagation. Designer call; defer.

### 9.4 Affinity-shift causality chain

The `<AffinityShift>` directive (per `wns_affinity_modifier_tool.md`) is deterministic — it updates faction state. But it doesn't currently CHAIN. If NL3's `<AffinityShift>` on `faction:moors_raiders` -0.15 fires, the next NL3 firing's narrative should reflect "the moors raiders are weakened in this district" as a prompt context input. **The affinity_resolver stores the shift; the WMS context builder doesn't yet read from it.**

Suggested fix: extend `build_wms_brief` to include recent affinity-shift records for factions/NPCs whose tags appear in active threads. Bridges narrative → state delta → narrative loop. Cross-tool concern: affects ALL weaver firings, not just one purpose.

`[WNS-GAP]` candidate — read-path enrichment from affinity ledger.

### 9.5 Player-facing chronicle voice variant

Today every layer has ONE voice. Speculative: per-player chronicle variants. A player playing as a moors raider sees the moors-stone narrative in a sympathetic voice; a player playing as the watch sees it in an opposing voice. **Faction-bound chronicler.** Very large design surface; defer. Could be implemented as a per-player narrative slice over the same shared WNS store (one chronicler-voice prompt variant per faction affinity band).

### 9.6 NL1 weaver — the missing seventh

NL1 is currently NOT a weaver. It's deterministic capture. But the existing NPC dialogue (`speechbank.idle_barks`, `speechbank.quest_offer`) could be LLM-authored against the NL2 firing's context — a chatty NPC-mouth weaver. **Different from `wes_tool_npcs` which authors the static NPC.** This `nl1_speaker` weaver would adapt the NPC's dialogue lines to current narrative state.

Today, speechbank dialogue is static post-NPC-creation. A future enhancement: an LLM-driven runtime adapter that takes the NPC's static speechbank + current WNS state and produces current-firing dialogue. Cross-feature concern with NPCs; deferred to NPCs agent's scope.

### 9.7 Eight-purpose-per-six-layer firing-guidance authoring

Speculative as a designer task, not a new endpoint: a Prompt Studio editor view specifically for the `_wes_tool` body per (purpose, layer) pair. 48 cells. Each cell holds 100-200 words of when-to-fire + body-shape guidance. The Prompt Studio (`tools/prompt_studio_main.py`) is the natural home. Suggested next-step after consolidation: add a "WNS Purpose Matrix" tab to Prompt Studio that surfaces the 48 cells and lets the designer author them in one pass.

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Close the `BundleToolSlice` narrative-context leak.** Extend the slice to carry `firing_layer_summary`, `parent_summaries`, `geographic_chain`, `wms_events_since_last`, and full thread payloads (not just headlines). Extend planner + hub `_make_vars` accordingly. Update planner and hub prompt fragment files with new template variables. **Single PR; all 8 content tools win.** Mirrors Agent 1 §4.4 and extends to additional fields the other 7 traces will surface.
2. **Build the player-facing journal / event-popup UI.** Today nothing presents WNS narrative to the player. The standalone-narrative deliverable does not exist as a player surface. New module(s) in `rendering/`; new bus event `WNS_NARRATIVE_FIRED` published by the weaver; new schema fields (`severity` at all layers, `headline`, `entity_refs`, `read_at`). **The standalone artifact has no consumer.**
3. **Designer prose furnishing.** Per CLAUDE.md v8.1 "designer-grindable state" — review every `_layer_scope`, every per-tag fragment, every `_wes_tool` body, every `_affinity_shift_tool` body across `narrative_fragments_nl2-7.json`. Plus the new per-purpose-per-layer firing guidance (~48 cells). Highest single source of "good narrative" quality delta.

Everything else in this trace — multi-directive compression, archive querying, affinity-causality chain, speculative endpoints — is downstream of those three.
