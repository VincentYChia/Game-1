# Feature Trace 08 — Chunks

**Wave:** 2
**Owned endpoints:** `wes_tool_chunks`, `wes_hub_chunks`
**Final output artifact:** `ChunkTemplate` JSON — a biome RECIPE (not a chunk instance) committed into `Definitions.JSON/Chunk-templates-generated-*.JSON` and overlaid onto the sacred `Chunk-templates-2.JSON` library by `ChunkTemplateDatabase`. Each template is consumed by `systems/chunk.py:_determine_chunk_type` (geographic dispatch) and `systems/chunk.py:_spawn_from_template` (resource density roll) when the player steps onto an unloaded chunk whose `GeographicData.chunk_type` resolves to that template.
**Date:** 2026-05-26

> "Chunks are the one WES tool where the runtime is fully wired. The pipe to the world exists. The thing left to make is the *world the pipe ships*."

This trace is anchored on a player walking east into a chunk that didn't exist before. Every decision below is in service of that chunk feeling like it BELONGS where it sits — that the moors flow from the salt-coast that flows from the lowland forest, that a swamp does not abut a desert without narrative reason, that the resources and enemies on it earned their right to be there from the WNS arc that conjured them.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

Player walks east. The screen pans. A boundary they have not yet crossed clicks under their feet — the next 16×16 tile chunk streams in. Tiles paint left-to-right as the chunk's seed rolls: ground type, foliage scatter, water shimmer, then resource nodes anchored to non-overlapping positions, then enemy patrols loaded from the chunk's spawn pool. The player sees: a windswept heath of rust-veined cliffs sloping into bog flats. Green-tinged copper seams glint where a thin morning sun catches them. Three rusted standing-stones cluster at the chunk's northeast edge — visibly the work of hands, not weather. A pair of copperlash riders graze their oxen at the south edge, two screen-lengths off. The player exhales, takes a quick mental inventory, and decides whether to skirt or engage.

That's the moment. The chunk template generation pipeline exists to make THAT moment feel earned.

### 1.2 Timing budget — the architectural constraint

Chunk template generation is asynchronous to player exploration. The pipe is:

- WNS NL4 (region) — and occasionally NL5 (province) for political-territory chunks — fires `<WES purpose="new-chunk">`.
- Planner emits a `chunks` step in the resulting plan.
- Hub fans the step into one or more `ExecutorSpec` entries.
- Tool generates a single `ChunkTemplate` JSON.
- ContentRegistry validates xrefs, runs orphan detection (referenced `resourceDensity` nodeIds and `enemySpawns` enemyIds must exist on disk or be co-emitted in the same plan), commits the file to `Definitions.JSON/Chunk-templates-generated-<ts>.JSON`, and triggers `ChunkTemplateDatabase.reload()`.
- The next chunk instance generated whose `GeographicData.chunk_type` resolves to a registered `geo_type` of that template begins using the new recipe.

**This is what makes chunks special among the 8 tools**: chunks are template-level, not instance-level. The player does NOT see a generated chunk the moment the WES tool fires. The player sees a generated chunk the next time the world generator rolls a `geo_type` that the new template handles, which could be the next chunk loaded or many sessions later. Latency budget at the WES tool layer: essentially unbounded — minutes are fine. Latency budget at the *player's chunk-load moment*: **zero LLM** — chunk loading is a deterministic lookup against the in-memory template database. There is no scroll-unfurl beat to mask anything.

User direction from architecture: the entire WES content pipeline is "make and store for seamless experience." For chunks this is even more relaxed than quests, because there is no acceptance-time materialisation step. Once committed, a chunk template is timelessly available. **Implication: we should be willing to spend more LLM budget per template** — more context, more reasoning, more cross-pollination — because we pay it once and reuse it forever.

### 1.3 Failure modes — what BAD looks like

Four flavors, ranked by likelihood and corrosiveness:

**(a) Stagnant predictability.** The world generator rolls "forest" 50% of the time and `ChunkTemplateDatabase.get_for_geo_type("forest")` always returns `peaceful_forest`. The player walks for an hour and sees `peaceful_forest, peaceful_forest, dense_forest, peaceful_forest, dangerous_forest, peaceful_forest`. They have learned the shape of "forest" and there is no surprise left. The generation pipeline could have generated ten new forest templates differentiated by region-arc, faction-territory, or narrative-stage, but instead the geo dispatch is a 1:1 map and the new templates never get reached. *(Defense: rich dispatch keys — not just `forest` but `salt_moors_forest`, `valdren_pinewood`, `silent_order_grove`. The `geoTypes` array on each generated template should declare these. The biome-string vocabulary the geographic system emits has to grow alongside templates.)*

**(b) Slop.** A template comes back: `{chunkType: "swamp_001", resourceDensity: {generic_herb: moderate}, enemySpawns: {generic_slime: moderate}, narrative: "A swamp."}` The schema validates. The xref check passes (both ids exist). The chunk loads. The player walks into it and feels nothing — there is no signature feature, no faction occupancy, no narrative anchor, no progressive tier signal. This is the fantasy-biome-shaped object. *(Defense: tier_anchor must mean something; the narrative line must name a signature feature; the resourceDensity must include at LEAST one signature resource at `very_high` density and at most three moderate accents; the metadata.tags must contain at least one region-coupling tag like `mid-game`, `legendary-ore`, `mythical-materials`, `transition`.)*

**(c) Craziness — the adjacency violation.** The generator coins `tropical_jungle_chunk` and the geo dispatch maps `forest → tropical_jungle_chunk`, putting palm-tree biome adjacent to the player's home pine woodland. Or: the WNS fires from `region:salt_moors` (a coastal heath thread) and the tool generates a desert chunk, because the directive_text said "harsh terrain" and the tool didn't see that the region's geographic context already says coastal-heath. The chunk is unforgettable and incoherent. *(Defense: the planner MUST thread `bundle.directive.scope_hint.geographic_chain` through to the hub's `address_hint` AND into the tool's user_template — the tool currently sees only `address_hint` as a string. The tool must see the parent region's biome and the firing locality's biome. Without that, the tool guesses.)*

**(d) Disconnected from the WNS arc.** This is the most corrosive long-term. The WNS thread that fired the directive said "the salt moors are restructuring around copper trade — rust-veined cliffs, new mining camps, the copperlash raiders working the high trails." The tool returns `dangerous_quarry_v2: {resourceDensity: {iron_deposit: high, granite: high}, enemySpawns: {wolf_grey: moderate}}`. Schema OK, xref OK. But there is no copper, no copperlash anything, no narrative connection to what the WNS just spent 30 events earning the right to say. The template is fine in isolation; it is wrong as the answer to the directive that generated it. *(Defense: as with quests, this is the `BundleToolSlice.parent_summaries` leak. The directive text is the seed; the parent narrative is the soil. Right now only the directive text reaches the tool.)*

### 1.4 What "good" actually looks like

A good generated chunk template, in the player's words after an hour of exploration: *"I figured out that when I'm in copperlash territory the cliffs look different — there's that green-glint stone, and the bogs taste of brine, and the raiders are up on the trails. When I'm in Brother Galen's chapel-province the chunks have those overgrown sanctuary ruins."*

Three properties:
- **Geographically legible** — the chunk feels like an extension of its neighbors. Forest flows to wetland flows to lake. No teleportation surprises.
- **Narratively legible** — the chunk's signature features (resource density profile, signature enemy, named anchor) point back to a WNS thread the player can name.
- **Progressionally legible** — the resource tier mix and enemy tier band match what the player would expect at that point of the world (close-to-spawn = low tier; far frontier = high tier).

### 1.5 Why chunks need less reciprocity than quests but more spatial discipline

Agent 1 (quests) flagged chunks as needing less narrative reciprocity. Correct — chunks are the spatial substrate; NPCs, hostiles, materials, quests *live inside* chunks, not the other way. A chunk doesn't need to know which quest references its `chunk_id` for an explore objective; the quest knows the chunk. But that ASYMMETRY of narrative reciprocity is matched by an ASYMMETRY of dependency direction: chunks are the **dependency root** of WES content (well, near-root — chunks depend on nodes and hostiles, which depend on materials, which is the actual root). The hub_dependency_resolver static analysis confirms this: `chunks → nodes → materials` and `chunks → hostiles → materials/skills`. A chunk template that references `moors_copper_seam` (a node) which yields `moors_copper` (a material) can cascade upstream generation. If the chunks tool is allowed to trigger that cascade reactively (memory: `hub_dependency_resolution.md`), one `<WES purpose="new-chunk">` directive can spawn the chunk + 2 nodes + 3 hostiles + 4 materials + ability set, atomically committed.

This is BOTH the most powerful and the most dangerous coupling in the system. Powerful because one well-targeted region-arc firing can populate an entire new biome's worth of content in one pass. Dangerous because if the planner or hub gets sloppy about constraining the cascade, one chunk firing can balloon into 15+ generations, blow through the per-bundle budget, and produce a flood of half-coherent stuff. **The cascade discipline has to live in the chunks tool's prompt itself — it must be biased toward referencing existing content first, co-emitting second, escalating to reactive resolution third.**

---

## 2. Output artifact schema completeness audit

The `ChunkTemplate` shape is locked in `data/databases/chunk_template_db.py:107-135` as the dataclass loaders, but the actual schema the LLM emits matches the JSON shape of `Chunk-templates-2.JSON`. Every field below must be filled by the tool or supplied as a defensible default. The "Author" column names which.

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `chunkType` | str (snake_case, unique) | `wes_tool_chunks` | Must encode biome + region/territory + tier band when possible. `dangerous_copper_moors` beats `dangerous_quarry_017`. Must be unique against `ChunkTemplateDatabase.list_chunk_types()`. |
| `name` | str (Title Case) | `wes_tool_chunks` | Evokes geographic identity. "Rust-Veined Moors" beats "Dangerous Quarry". Mirrors `chunkType`'s flavor. |
| `category` | enum: peaceful/dangerous/rare/water/rare_water | `wes_tool_chunks` | Drives `WorldGenerationConfig.get_danger_distribution()` resource scaling tier; must align with region's expected danger band. |
| `theme` | enum: forest/quarry/cave/water | `wes_tool_chunks` | The dominant resource-type hint. Drives fallback resource spawning in `systems/chunk.py:_spawn_resources_fallback` when template's `resourceDensity` is empty. |
| `resourceDensity` | Dict[resource_id → {density, tierBias}] | `wes_tool_chunks` | density ∈ {very_low, low, moderate, high, very_high} mapping to {0.5x, 0.75x, 1.0x, 2.0x, 3.0x} spawn weights; tierBias ∈ {low, mid, high, legendary}. SIGNATURE rule: at least one resource at `very_high` density to give the chunk a "this is the X biome" identity. Accent resources at `low` for variation. |
| `enemySpawns` | Dict[enemy_id → {density, tier}] | `wes_tool_chunks` | Same density allow-list. Tier 1-4 integer per enemy entry. EMPTY allowed (peaceful chunks); MUST be empty for water_lake/water_river. |
| `generationRules.rollWeight` | int 1-10 | `wes_tool_chunks` | Relative biome selection weight when geo dispatch falls through to roll-based legacy generation. Higher = more common. Sacred peaceful=5, dangerous=3, rare=1. New templates that ride a specific geo_type can use rollWeight=0 (only triggered by dispatch). |
| `generationRules.spawnAreaAllowed` | bool | `wes_tool_chunks` | Currently decorative — `systems/chunk.py` never reads this. Emit truthfully (peaceful only) for forward-compat. |
| `generationRules.adjacencyPreference` | List[chunkType] | `wes_tool_chunks` | Currently decorative — not enforced in code. **THIS IS WHERE NARRATIVE-COHERENT BIOME ADJACENCY LIVES** even if unused. See §8.2. Emit sensible neighbors (matching theme + category band). |
| `generationRules.edgeOnly` | bool | `wes_tool_chunks` | Water-chunk specific; sacred file uses this for `water_lake` / `water_river`. New water chunks should set true. Currently not read by code but is by `WorldGenerationConfig.water_chunks.*` distribution math. |
| `generationRules.minDistanceBetween` | int | `wes_tool_chunks` | Same — sacred file uses this; not yet enforced in code. |
| `tilePattern` | Optional[Dict] | `wes_tool_chunks` | Water-chunk-specific. `{waterCoverage: float, hasIslands: bool, shoreWidth: int, hasBridge?: bool, isToxic?: bool, riverWidth?: int}`. Land chunks should omit. Currently not read by chunk.py's water-tile generator (it has hardcoded lake/river/swamp logic), but emit truthfully for forward-compat. |
| `geoTypes` | List[str] | `wes_tool_chunks` | The KEYS the geographic system emits that should dispatch to this chunk. `["forest", "salt_moors_forest"]` etc. Used by `ChunkTemplateDatabase._auto_register_geo_types` to add new geo_type → chunkType entries WHEN the sacred `geo_chunk_dispatch.json` does not already claim that geo_type. **This is the runtime hook — if `geoTypes` is empty or only contains keys the dispatch already maps, the new template will not be reached by the world generator.** |
| `metadata.narrative` | str (2-3 sentences) | `wes_tool_chunks` | Player-facing flavor: the SIGNATURE FEATURE, MOOD, THREAT CHARACTER. The chronicler-voice description. Must name what distinguishes this template from siblings of the same category+theme. |
| `metadata.tags` | List[str] (3-6) | `wes_tool_chunks` | Drawn from the allow-list (see §2.1). The biggest diversity signal — these tags will be read by retrieval at every layer above (WNS query by tag, future quest hub for `expiration.chunk_id`, NPC tool for `home_chunk`). |
| `source` | str ("sacred"/"generated") | (set by loader, NOT LLM) | The database stamps this on load — generated templates always win on collision with sacred unless dispatch explicitly maps geo_type to a sacred entry. |

### 2.1 Tag allow-list (current sacred + generated vocabulary)

From `prompt_fragments_tool_chunks.json` + `Chunk-templates-2.JSON`:

```
ancient, barren, cave, combat, crystal, dangerous, deep, dense, edge-only,
end-game, exposed, fishing, forest, harsh, highlands, legendary-ore,
legendary-wood, marsh, mid-game, mixed, mixed-quality, mythical-materials,
ore-quality, overgrown, peaceful, quarry, rare, rare-ore, ruins, safe,
starter, stone-rich, transition, water, wood-quality, wood-rich
```

These tags carry game-functional weight — `starter`/`mid-game`/`end-game` correlates to expected player level, `dangerous`/`peaceful` correlates to `category` (and SHOULD match), `fishing` flags the water subtype, `legendary-ore`/`legendary-wood` signals tier band. Per memory `tag_system_functionality.md`, NEW tags MUST be prefixed `NEW:` for designer review. Silent invention is silent functionality loss.

### 2.2 Schema completeness — what's MISSING

`[WES-SCHEMA-GAP]` audit. The current schema vs. what the design needs:

- `[WES-SCHEMA-GAP]` **`evolution_parent_id` / `evolution_child_ids` / `evolution_chance`** — per memory `chunk_evolution_future_idea.md`, post-release we want chunk templates organized into a branching tree where individual chunk instances have a small chance to evolve down their template's branch (`peaceful_forest → ancient_grove → primeval_wood → worldtree_glade`). DO NOT implement pre-release. **Leave the fields in the schema as optional** so designer authoring can begin to fill them out without a future migration. Tool should emit empty strings / 0.0 by default; database loader should tolerate missing.
- `[WES-SCHEMA-GAP]` **`signature_feature` slot** — currently the "what's distinctive" is buried in `metadata.narrative` prose. Designer ledger and the WNS retrieval would benefit from a structured `signature_feature: {type: enum, name: str, description: str}` field (e.g. `{type: "landmark", name: "Standing Stones of Rust", description: "..."}`). Useful for: NPC tool when an NPC's locality contains a signature; quest tool when an explore objective wants to anchor to "the chunk with the standing stones." Workaround: parse from narrative prose. Better: structured field.
- `[WES-SCHEMA-GAP]` **`region_anchor` / `wns_thread_id`** — chunk templates currently have NO link back to the WNS thread that generated them. A chunk born from "the salt moors restructuring around copper" thread should carry `wns_thread_id` so future WNS firings on that thread can find their physical embodiment. **Mirror to quests' `wns_thread_id` field**. Workaround: the `ContentRegistry.reg_chunks` row has a `source_bundle_id` column that traces back to the firing bundle, which traces back to the source narrative row — but that is two joins removed from a thread_id. Cleaner: write `wns_thread_id` directly on the template.
- `[WES-SCHEMA-GAP]` **`tier_anchor`** — the hub's `hard_constraints.tier_anchor` exists in the hub prompt's spec but does NOT make it onto the committed template. The template only carries per-resource `tierBias` and per-enemy `tier`. There is no top-level "this chunk is intended for player level X-Y." Hub-level intent gets dropped at commit time. Workaround: it's implicit in the resource tier distribution and enemy tier mix. Cleaner: explicit `tier_anchor: int` on the template, used by future quest difficulty calculator and player-fit signals.
- `[FRAGMENT-GAP]` **Faction territory linkage.** Sacred templates have no concept of "this chunk is moors_raider territory." If a chunk is born from a faction-arc WNS thread, the faction tag should be carried explicitly. Currently the chunk's faction occupancy is implied only by which hostiles spawn there (`copperlash_rider` is moors_raiders faction). Cleaner: `metadata.controlling_faction: str` or `metadata.faction_tags: [str]`. This is the hook FactionSystem (Phase 2+) needs to surface "where does faction X actually live in the world."
- `[FRAGMENT-GAP]` **Named place anchors.** Sacred templates have no notion of named POIs within the chunk — the player sees "rust-veined cliffs" because the narrative says so, but the chunk doesn't model "there is a specific landmark at tile (5, 12) called the Standing Stones of Rust." Memory `quest_lifecycle_design.md` flags that quest archives want `participating_entities` including "chunks touched" — that linkage is by chunk_id only, not by named feature. For future post-release evolution work (memory: `chunk_evolution_future_idea.md`) the named-place anchor concept becomes essential.
- `[FRAGMENT-GAP]` **Ambient-hazard / weather slots.** Sacred templates have `isToxic: true` on `water_cursed_swamp` and nothing else. There is no representation of "this chunk has acid rain at night" or "this chunk has ambient mana storms that buff enchanting." Player progression and quest difficulty are flat across chunks of the same category+theme today. Cleaner: `ambient_effects: List[{trigger, effect, magnitude}]`. NOT urgent — leave as future TODO.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a 1990s systematic generator with no LLM produces, given category + theme + a tier band:

```json
{
  "chunkType": "dangerous_quarry_042",
  "name": "Dangerous Quarry",
  "category": "dangerous",
  "theme": "quarry",
  "resourceDensity": {
    "iron_deposit": {"density": "high", "tierBias": "mid"},
    "copper_vein": {"density": "moderate", "tierBias": "low"},
    "granite_formation": {"density": "moderate", "tierBias": "low"}
  },
  "enemySpawns": {
    "wolf_grey": {"density": "moderate", "tier": 1},
    "slime_green": {"density": "moderate", "tier": 1}
  },
  "generationRules": {
    "rollWeight": 3,
    "spawnAreaAllowed": false,
    "adjacencyPreference": ["dangerous_quarry", "dangerous_cave"]
  },
  "geoTypes": ["quarry"],
  "metadata": {
    "narrative": "A dangerous quarry. Watch for enemies.",
    "tags": ["quarry", "combat", "ore-quality", "mid-game"]
  }
}
```

This is fine. This is also exactly the slop the player has seen in a thousand worlds. Schema-valid, runtime-functional, narratively silent. The chunk loads, the player walks through it, the player forgets it within minutes. The `geoTypes: ["quarry"]` line means this new template will compete with the existing `peaceful_quarry` for the `quarry` dispatch slot, and since generated wins on collision, this template REPLACES the peaceful one — which means every "quarry" chunk in the player's world is now this generic dangerous template. **This is a sneaky failure mode: a single bad generated template can suppress an entire sacred biome by claiming its dispatch key.**

### 3.2 What we have to add to exceed this

Field-by-field, what the LLM must contribute that the slot machine can't:

1. **`chunkType`** — name must encode region and faction or signature. `dangerous_copper_moors` not `dangerous_quarry_042`. Needs `address_hint` (region name) + `directive_text` (faction or signature theme) + `recent_registry_entries` (uniqueness check).
2. **`name`** — Title Case version with cultural taste. "Rust-Veined Moors" not "Dangerous Quarry". Needs `flavor_hints.name_hint` + the region's geographic descriptor (the `tier_briefs[i].name` in `scope_hint.geographic_chain`).
3. **`resourceDensity`** — signature resource at `very_high` (the thing this biome is FOR), 1-2 supporting at `high`/`moderate`, 1-2 accents at `low`. Slot machine picks evenly; we want a TASTE. Needs `cross_ref_hints.primary_resource_ids` from the hub + the planner's understanding of which materials/nodes the region's WNS arc has been talking about.
4. **`enemySpawns`** — same shape: ONE signature antagonist at `high`/`very_high`, supporting wildlife at `moderate`/`low`. Slot machine puts wolf_grey everywhere; we want a SIGNATURE.
5. **`metadata.narrative`** — names the signature feature (the rust-veined cliffs, the standing stones, the green-copper glint), the mood (windswept, brine-tinged), the threat character (raiders working the high trails). Slot machine: "Watch for enemies."
6. **`metadata.tags`** — pulled from the allow-list but selected to encode region-coupling. `harsh`, `exposed`, `mid-game`, `ore-quality`, `combat` for moors. Not `quarry, combat, ore-quality, mid-game` blindly stamped.
7. **`generationRules.adjacencyPreference`** — sensible biome neighbors. The moors abut `rocky_highlands` and `dangerous_quarry`, NOT `peaceful_forest` and `water_lake`. This list is currently not enforced in code but is the SCAFFOLDING for future adjacency-aware world generation. Treat it as the chunk's "where I belong" declaration.
8. **`geoTypes`** — the dispatch keys this template claims. The slot machine claims the obvious one (`quarry`) which collides with existing peaceful. The LLM should claim NARROWER keys (`salt_moors_quarry`, `copper_moors_quarry`) and let the existing peaceful keep `quarry`. **This is the load-bearing line that prevents new generated templates from suppressing sacred biomes.** Designer-tunable rule: every generated template should declare AT LEAST ONE narrowed `geoTypes` key that doesn't collide with sacred, OR explicitly claim a sacred key with intent to replace.
9. **`tilePattern`** — water-chunk shape parameters (coverage, shore width, islands, toxicity). Slot machine emits defaults; LLM should pick water-chunk-specific values that match the narrative (a `water_cursed_swamp` wants `isToxic: true, waterCoverage: 0.5, hasIslands: true`).

The delta is: **regional specificity, signature feature naming, dispatch-key narrowing, and adjacency coherence.** Everything in the chunks pipeline architecture must serve these four properties.

---

## 4. Backward trace through the pipeline

Rung-by-rung walk from "player walks into a generated chunk" backward to "WMS event row."

### 4.1 Rung 0 — Player enters new chunk (player-facing)

Consumes: `ChunkTemplate` (looked up by `_determine_chunk_type`) + `WorldGenerationConfig` resource count + per-chunk seed.
Emits: `Chunk` instance with tiles + resources + (no enemies yet — `Combat/combat_manager.py` weighs spawn pool against template's `enemySpawns` separately).
Risk: if `_determine_chunk_type` returns a `chunk_type` whose template isn't loaded, `ChunkTemplateDatabase.get_for_geo_type` returns None and `_spawn_from_template` falls through to the substring-matched legacy fallback (`db.get_resources_for_chunk(self.chunk_type, tier_range)`). The chunk still generates, but loses its custom density profile.

### 4.2 Rung 1 — `ChunkTemplateDatabase.reload()` (post-commit)

Triggered by `world_system/content_registry/database_reloader.py` after `ContentRegistry` writes a generated file. Reload:
- Re-reads sacred `Chunk-templates-*.JSON` + all `Chunk-templates-generated-*.JSON`.
- Re-loads `geo_chunk_dispatch.json`.
- Auto-registers any generated template's `geoTypes` array that doesn't collide with sacred dispatch.

Output: in-memory template database swapped atomically. Next chunk load uses new templates. **Already-rendered chunks DON'T regenerate** — they retain the template they were built from. This means a player loaded into the world for an hour will see new chunks only at the exploration frontier; existing chunks keep their existing identity. This is correct (per memory `chunk_evolution_future_idea.md`'s "chunks are immutable post-generation" rule) but it means the cadence question becomes: **how often does the player walk into virgin territory vs. revisit known territory?** Generated chunk templates only "land" on virgin chunks. If the player is grinding a known region, new templates accumulate but aren't seen.

What's MISSING:

- `[FRAGMENT-GAP]` **Visibility loop**: there's no signal back to the WNS that "the player saw the generated chunk template `dangerous_copper_moors` for the first time." Without that, the WNS doesn't know whether the content it generated has been delivered to the player. The story-continuity loop is open at this end. Workaround: a `chunk_template_first_seen` WMS event could close the loop; not implemented today.

### 4.3 Rung 2 — `wes_tool_chunks` (one ExecutorSpec → one chunk-template JSON)

Inputs (from `prompt_fragments_tool_chunks.json:user_template`):

```
Spec id: ${spec_id} (plan step ${plan_step_id})
Item intent: ${item_intent}
Hard constraints: ${hard_constraints}
Flavor hints: ${flavor_hints}
Cross-ref hints: ${cross_ref_hints}
```

Output: one `ChunkTemplate` JSON matching the `Chunk-templates-2.JSON` shape.

What's MISSING:

- `[WES-SCHEMA-GAP]` **The geographic chain is dropped.** Just like quests, the chunks tool only sees the `address_hint` string (e.g. `"region:salt_moors"`) but does not see the structured `geographic_chain` that the WNS-to-WES bridge built (`world_system/wns/wns_to_wes_bridge.py:99-130`) — the tier_briefs with each ancestor region's name, biome, description, and tags. **This is the single largest source of "stagnant" failure: without the parent region's biome on the input, the tool cannot pick narratively-coherent `geoTypes` keys, cannot honor adjacency to the existing world, and falls back to template names like `dangerous_quarry_042`.** Fix: extend the tool's user_template with `${geographic_chain}` slot; have the planner thread it through into hub's `flavor_hints` → tool's `${geographic_chain}`. Alternative: pass the full `BundleToolSlice` with `scope_hint.geographic_chain` preserved.
- `[WES-SCHEMA-GAP]` **The `parent_summaries` leak (same as quests).** The bundle's `narrative_context.parent_summaries` (the NL5 province narrative + the NL4 region narrative + the self-narrative the weaver just wrote) is stripped by `slice_bundle_for_tool` at `living_world/infra/context_bundle.py:342-370`. The tool sees only `directive_text` and the focal-address open threads. The salt-moors-restructuring-around-copper narrative reaches the tool only via the 1-2 sentence `<WES purpose="new-chunk">body</WES>` body. **This is why a chunk born from a rich WNS thread can come out narratively generic.** Fix at the slice layer benefits chunks AND quests AND every other content tool. *(Agent 1 already flagged this. I'm echoing the priority.)*
- `[FRAGMENT-GAP]` **The recent geographic registry context — what biomes/templates already exist in the firing region's parent chain.** The tool currently has no way to see "the parent province has 3 forest templates, 2 quarry, 0 cave, 1 water." Without that, the tool can't make informed adjacency choices or claim narrowed `geoTypes` keys that don't collide. Hub or orchestrator should attach `${neighboring_templates}` (the templates already mapped to the parent region/province's geo_types) and `${registry_template_summary}` (counts by category + theme across the world).
- `[FRAGMENT-GAP]` **Player progression band.** The tool doesn't see what player level the average explorer is at. A region close to spawn should generate templates with low `tier_anchor`; a frontier region should generate higher. Currently `tier_anchor` comes from the planner via hub's `hard_constraints.tier_anchor` — and the planner has to infer it from `firing_tier` × the bundle's geographic distance from spawn. Acceptable for v4; could be enriched by adding `${player_progression_band}` (median player level in this region or globally).
- `[FRAGMENT-GAP]` **Co-emitted artifact awareness.** When the planner co-emits a `nodes` step before the `chunks` step (because the chunk references new `moors_copper_seam`), the chunks tool sees only the cross-ref id, not the node's narrative. So the chunk can't easily say "the rust-veined cliffs are where the moors copper seeps through." Fix: when a chunks step depends on an upstream step, the dispatcher should attach the upstream artifact's summary to the chunks tool's input (`${coemitted_artifact_summaries}`).

### 4.4 Rung 3 — `wes_hub_chunks` (one plan step → batch of ExecutorSpecs)

Inputs (from `prompt_fragments_hub_chunks.json:user_template`):

```
Plan step id: ${plan_step_id}
Step intent: ${step_intent}
Step slots: ${step_slots}
Directive framing: ${directive_text}
Focal address: ${address_hint}
Active thread headlines: ${thread_headlines}
Recent chunk registry entries (avoid duplication): ${recent_registry_entries}
```

What the hub does: takes "a new dangerous moors biome featuring rust-veined cliffs and copper seams" and emits 1-N `<spec>` elements. The hub_prompt's example shows exactly the right shape (one spec, with `hard_constraints.biome='moors'`, `hard_constraints.tier_anchor=2`, `flavor_hints.adjacency_intent=['rocky_highlands', 'dangerous_quarry']`, `cross_ref_hints.primary_resource_ids=['moors_copper_seam']`).

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same `parent_summaries` leak.** Hub's `slice_bundle_for_tool` view doesn't carry parent narrative. The hub sees the directive text but not the province-scale tide that birthed the regional arc.
- `[FRAGMENT-GAP]` **`recent_registry_entries` populated by caller.** This slot is the diversity guard (avoid duplicating recent chunk templates). It's passed in by the orchestrator as a parameter to `slice_bundle_for_tool`. **Currently the orchestrator-side wiring populates this only when explicitly invoked; the default plan-dispatcher path doesn't pass anything.** Verify wiring before relying on the diversity guard. *(Same issue Agent 1 flagged for quests — shared fix.)*
- `[FRAGMENT-GAP]` **`geographic_chain` doesn't reach hub either.** Same leak as the tool. The hub uses `address_hint` as a string. Without the chain, hub can't author `cross_ref_hints.primary_resource_ids` against the right region's materials, and can't pick `geoTypes` that narrow correctly.
- `[FRAGMENT-GAP]` **Co-emission coupling.** When the planner emits `[nodes, hostiles, chunks]` with chunks depending on both, the hub doesn't see the co-emitted node and hostile specs' identifiers + tags. The hub has to GUESS the new node/hostile names and put them in `cross_ref_hints.primary_resource_ids` / `primary_enemy_ids` — and if it guesses wrong, the orphan detector blocks commit. Fix: dispatcher should attach `${coemitted_specs_summary}` (the upstream specs' ids + intent prose) to the chunks hub's input.

### 4.5 Rung 4 — `wes_execution_planner` (one bundle → one plan DAG)

The planner is the ONE place where the full bundle is in play. It chooses when to emit a `chunks` step (firing_tier ≥3 typically, occasional at tier 4 for region arcs and rare at tier 5 for province-scale territorial conquests).

Inputs (from planner prompt):
- `bundle_id`, `firing_tier`, `firing_address`, `bundle_directive` (the `<WES purpose="new-chunk">body</WES>` body), `bundle_narrative_context`, `bundle_delta`, `thread_headlines`, `registry_counts`.

What's MISSING:

- `[FRAGMENT-GAP]` **The `bundle.directive.scope_hint.geographic_chain` is in the bundle but not in the planner's prompt template.** The planner sees `firing_address` and `firing_tier`, but the `scope_hint.geographic_chain` array (the tier_briefs with parent region biomes, names, tags) is not wired into the prompt. For chunks especially, this is a load-bearing input — the planner is choosing not just "do we need a chunks step" but "what biome should the chunks step ask for, given the region's existing biome." Without the chain, the planner is blind to existing biome distribution.
- **Scope by firing tier prose**: NL5 (province) explicitly says `avoid: new-chunk, new-material, new-hostile` (memory: `narrative_fragments_nl5.json:19`). NL4 (region) lists `new-chunk` as a typical purpose. NL3 (district) doesn't list it (which is right — district-scale arcs should usually flow nodes/hostiles into existing chunks, not coin new biomes). NL2 (locality) never fires `new-chunk`. **This is correctly designer-tuned today.** But the planner's `scope_by_firing_tier` prose needs to reinforce that — "a tier-3 firing should rarely emit a chunks step; a tier-4 firing makes chunks a top candidate; a tier-5+ firing should emit chunks only when the province tide names a new territorial frontier."

### 4.6 Rung 5 — WNS NL4 weaver emits `<WES purpose="new-chunk">`

NL4 (region) is the natural home (memory: `narrative_fragments_nl4.json:19` lists `new-chunk` as a typical purpose). The fragment body should tell the weaver: name the biome's signature, name the region it opens up, name the threat or resource that gives it identity.

What's MISSING:

- `[WNS-GAP]` **Firing guidance for `new-chunk` specifically.** The current `_wes_tool` body says "a new biome type the region is opening up" — vague. The fragment should tell the weaver: fire `<WES purpose="new-chunk">` when:
  - A regional WNS thread has named a new geographic feature ("the rust-veined cliffs," "the silent valley") and no existing chunk template can carry it.
  - The arc is in `rising_action` or `turning_point` (not `resolution` / `coda`).
  - The thread implies a faction has claimed new territory.
  - A region's economic restructuring implies a new resource cluster (e.g. copper-trade arc → new copper-rich biome).
  - **NOT** when the existing chunk library can carry the arc — slop suppression rule.
- `[WNS-GAP]` **Directive body specificity.** The body `<WES purpose="new-chunk">body</WES>` is freeform. A weaver might write "A new harsh biome." (slop). A good weaver writes "A windswept moors biome of rust-veined cliffs and boggy flats — territory of the copperlash raiders, rich in green-copper seams; tier 2 expected, hostiles include the riders themselves, resources include moors_copper_seam." The fragment should give the weaver: name the signature feature, name the controlling faction (if any), name the tier expected, name AT LEAST ONE resource and ONE enemy archetype (even if the weaver doesn't know they exist — the cascade resolver will handle creation).

### 4.7 Rung 6 — WNS reads WMS L2 interpretations + L4-L5 chronicle

For chunk-relevant signals, the weaver consumes `${wms_context}` — recent L2 interpretations whose addresses intersect the firing region. For chunks, the relevant L2 evaluators are:

- `gathering_regional.py` (resource depletion / abundance trends)
- `combat_kills_regional_*.py` (where high-tier hostiles are concentrated)
- `exploration_regional.py` (where the player has been pushing the frontier)
- `economic_regional.py` (resource trade flows that imply biome restructuring)

All of these are designer-reviewed and locked. The WMS gives us everything we need for chunk-arc context. Pure fragment-layer threading is what's missing.

### 4.8 Rung 7 — WMS L2 evaluators interpret L1 events

Solid. The 33 L2 evaluators have been reviewed and locked. No gap here for chunks.

---

## 5. Per-field provenance table

For EVERY field the LLM authors, where the upstream signal comes from. The 9-rung WMS column applies when a `[WMS-GAP]` might be tempting — walked in writing in §5.1.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `chunkType` | Tool prompt + `flavor_hints.name_hint` + `${geographic_chain}` (for region encoding) | Hub crafts name_hint from `step.intent` + `address_hint` | Partial — geographic_chain doesn't reach the tool | `[WES-SCHEMA-GAP]` — see 4.3 |
| `name` | Tool prompt + `flavor_hints.name_hint` | Hub Title Cases from `step.intent` | Yes | — |
| `category` | Hub `hard_constraints.category` | Hub picks from 5 based on `step.intent` + planner's firing_tier × geographic distance | Yes | — |
| `theme` | Hub `hard_constraints.theme` | Same as category | Yes | — |
| `resourceDensity` keys | Hub `cross_ref_hints.primary_resource_ids` + tool's own pool from existing registry | Hub names them from `step.slots` or relies on hub_dependency_resolver to co-emit nodes | Partially — co-emission via planner depends_on works; reactive resolution NOT yet implemented | `[FRAGMENT-GAP]` (planner-level wiring); memory `hub_dependency_resolution.md` documents intent |
| `resourceDensity` values (density+tierBias) | Tool prompt | Tool picks per-resource based on signature-vs-accent role + tier_anchor | Yes | — |
| `enemySpawns` keys | Hub `cross_ref_hints.primary_enemy_ids` + tool's own pool | Same as resourceDensity | Same | Same |
| `enemySpawns` values (density+tier) | Tool prompt | Tool picks per-enemy | Yes | — |
| `generationRules.rollWeight` | Tool prompt | Tier × narrative weight; tool picks 1-10 | Yes | — |
| `generationRules.spawnAreaAllowed` | Tool prompt | true only for category=peaceful | Yes | — |
| `generationRules.adjacencyPreference` | Tool prompt + `flavor_hints.adjacency_intent` | Hub picks neighbors from `address_hint` context | Partial — hub only sees `address_hint` string, not geographic_chain with neighbor biomes | `[FRAGMENT-GAP]` — see 4.4 |
| `generationRules.edgeOnly` | Tool prompt | true for water-themed | Yes | — |
| `generationRules.minDistanceBetween` | Tool prompt | Tool picks from category | Yes | — |
| `tilePattern.*` | Tool prompt | Water-chunk-only; tool picks | Yes | — |
| `geoTypes` | Tool prompt | **Load-bearing**: tool should claim NARROWED keys not sacred-collision keys | Yes — but no prompt guidance on collision-avoidance | `[FRAGMENT-GAP]` — tool prompt needs explicit "check if dispatch key would collide with sacred; prefer narrowed regional keys" rule |
| `metadata.narrative` | Tool prompt | Tool's signature-feature naming + mood from `directive_text` + parent narrative | Partial — parent narrative dropped at slice | `[WES-SCHEMA-GAP]` — see 4.3 |
| `metadata.tags[]` | Tool prompt | Tool picks 3-6 from allow-list | Yes (locked allow-list per `tag_system_functionality.md`) | — |

### 5.1 WMS-GAP walk — temptations and the 9 rungs

I was tempted twice. Both passed the 9-rung check; both produced `[FRAGMENT-GAP]` markers, not `[WMS-GAP]`.

**Temptation A: "The chunks tool needs to know the parent region's existing biome composition (what's the dominant terrain across the parent region's chunks)."**

I walked the 9 rungs:

1. **Direct query**: Is there a single WMS event "the parent region's biome composition is X"? No — biome composition is geographic-registry state, not an event. *But it's queryable.*
2. **Adjacent events**: `combat_kills_regional_*` produces address-tagged kill rows whose `event.source_chunk_type` (or, in some evaluators, embedded tag like `chunk:dangerous_forest`) tells you what biome the event happened in. Aggregating across a region's chunk-types from these rows gives biome composition. **Partial yes.**
3. **Negative patterns**: Absence of `chunk:water_*` events in a region tells you the region has no water. Aggregation gives proportion.
4. **Aggregation**: `daily_ledger` doesn't track chunk-type frequency. But `event_store.count_filtered(address=region:X)` partitioned by `chunk:*` tag gives the distribution.
5. **Trajectory**: Not relevant for biome composition (it's stable per region post-init).
6. **Cross-layer climb**: NL4 (region) narrative may explicitly say "the salt moors stretch from the river-fork to the high cliffs" — biome description embedded in chronicle. The bundle's `narrative_context.firing_layer_summary` carries this.
7. **Cross-entity composition**: `geographic_registry.get_region(region_id).child_ids` enumerates districts; each district's `tags` field carries biome tags (`biome_primary`).
8. **Stat / ledger lookup**: `geographic_registry.Region.biome_primary` field is the canonical, deterministic source of truth — **this is the cleanest single signal.** It exists at every tier of the hierarchy (LOCALITY → DISTRICT → PROVINCE → REGION → NATION).
9. **Trigger history**: Not applicable.

**Verdict**: NOT a WMS gap. The geographic_registry already carries everything we need. The actual gap is at the **WES bridge layer** — `wns_to_wes_bridge._build_scope_hint` writes `geographic_chain` with `tier_briefs[i].biome` AND `tier_briefs[i].tags` AND `tier_briefs[i].description`. The leak is that downstream (planner / hub / tool) prompt templates don't have a `${geographic_chain}` slot. Marker: `[FRAGMENT-GAP]` on the planner/hub/tool prompt input set.

**Temptation B: "The chunks tool needs to know what TIER of player content lives in this region (the median tier of recent gathering/combat at this address)."**

9 rungs again:

1. **Direct query**: Single event "median player tier at region X"? No.
2. **Adjacent events**: `combat_kills_regional_*` events carry `tier:N` tags on hostiles killed. `gathering_regional` events carry `tier:N` tags on nodes harvested. Aggregating gives a clean tier distribution per region.
3. **Negative patterns**: Absence of tier-3+ events at a region = low-tier region.
4. **Aggregation**: 33 L2 evaluators include tier-banded variants (`combat_kills_regional_low_tier.py`, `combat_kills_regional_high_tier.py`). These ARE the answer.
5. **Trajectory**: A region that started low-tier and trends high-tier (player progression) is exactly the signal the chunks tool wants to follow for tier_anchor.
6. **Cross-layer climb**: NL4 narrative may say "the region has grown to T3-appropriate threat levels" — the bundle's `parent_summaries` carries this *if we don't strip them at slice time*.
7. **Cross-entity composition**: Combine "tier of hostiles killed" + "tier of materials gathered" + "tier of skills unlocked" at this region = comprehensive tier band.
8. **Stat / ledger lookup**: `daily_ledger.tier_distribution_by_region` (does this exist? — partial, the evaluator output rows have this but not a single ledger field). Cleaner: `stat_store.get_region_tier_band(region_id)` — would need to be added but is deterministic.
9. **Trigger history**: Not applicable.

**Verdict**: NOT a WMS gap either. Rungs 2-4 give us everything. The gap is at the **planner/hub prompt layer** — `tier_anchor` should be DERIVED from these WMS aggregates, not authored by the LLM from narrative inference. Marker: `[FRAGMENT-GAP]` on the planner's input set — add `${region_tier_distribution}` as a computed scope variable.

**Zero `[WMS-GAP]` markers in this trace.** The WMS provenance is solid. Geographic_registry + 33 evaluators + bundle's `scope_hint.geographic_chain` give us everything. The gaps are at the WNS→WES boundary (parent_summaries leak), at the bridge→prompt threading layer (geographic_chain not in prompt templates), and at the tool prompt itself (no collision-avoidance rule on `geoTypes`).

This is consistent with Agent 1's finding for quests — the upstream sacred work (WMS + geographic_registry) is correct; the failures live at the WES boundary slicing/threading.

---

## 6. Cross-references with other features (personal shopper)

### 6.1 Heavy shared infrastructure (use as-is)

- **WNS NL4 narrative weaver** — shared with every content tool. Region-scope arc is the natural home for `new-chunk`. *(Agent: WNS / Planner+Supervisor.)*
- **WES Execution Planner** — shared. The `scope_by_firing_tier` rules govern when chunks are eligible. *(Agent: WNS / Planner+Supervisor.)*
- **WMS L2 evaluators + L2-L7 chronicle** — read-only shared substrate. *(Agent: WNS / Planner+Supervisor.)*
- **Tag system + tag-registry.json** — shared allow-list. Chunks' `metadata.tags` draws from it. *(Cross-cutting.)*
- **`BundleToolSlice`** — shared by all hubs. Parent_summaries leak (§4.3, §4.4) affects every tool equally. **Fix in one place benefits all 8.** *(Echoes Agent 1 priority.)*
- **Orphan detector** — shared. Cross-ref enforcement on `resourceDensity` and `enemySpawns` keys.
- **`hub_dependency_resolver`** — shared. Reactive upstream-tool triggering (memory: `hub_dependency_resolution.md`). Chunks are the highest-leverage tool for this because chunks → nodes → materials is the deepest dependency chain in the system. **Implementing reactive resolution for chunks single-handedly justifies the whole resolver.** *(Cross-cutting; no single owner — could go in WES tooling agent.)*

### 6.2 Chunks-specific shared with adjacent features

- **Nodes** — **TIGHTEST NEIGHBOR.** Chunks reference node IDs in `resourceDensity`. Every chunk needs nodes that exist or get co-emitted. When the WNS thread implies a new resource (e.g. "rust-veined cliffs of green-copper seams"), the planner emits `[nodes, chunks]` with chunks depending on nodes. **The nodes agent must define how its tool accepts `cross_ref_hints.spawned_in_chunk_id` so the node template can carry geographic-anchor flavor back ("this node primarily spawns in dangerous_copper_moors").** *(Agent: Nodes.)*
- **Hostiles** — **NEXT-TIGHTEST.** Chunks reference enemy IDs in `enemySpawns`. Same co-emission pattern as nodes. **The hostiles agent must accept `cross_ref_hints.native_chunk_ids` so the hostile's lore can flavor around territory ("the copperlash riders roam dangerous_copper_moors and dangerous_quarry").** *(Agent: Hostiles.)*
- **Materials** — **TRANSITIVE.** Chunks don't reference materials directly, but chunks → nodes → materials is the dependency cascade. If a chunk wants a brand-new resource cluster, the cascade can fire `[materials, nodes, chunks]` in one plan. Materials agent's job is to ensure its tool composes cleanly when triggered by node co-emission. Chunks don't need materials agent's prompt to change; just keep the dependency cascade clean. *(Agent: Materials.)*
- **NPCs** — Chunks are where NPCs live. NPC's `home_chunk` field references a chunk_id. **The NPCs agent's tool should accept `cross_ref_hints.home_chunk_id` from the chunk's locality.** When a new chunk template defines a settlement or named landmark, the NPCs agent may want to flavor the NPC around that signature. Reverse-direction reciprocity is weak here — the chunk doesn't need to know which NPCs live in it. *(Agent: NPCs.)*
- **Hostiles' abilities + Skills** — Even more transitive. If a chunk → hostile → skills cascade triggers, the skills agent's tool may fire. Chunks don't influence skills prompts directly. *(Agent: Skills — informational only.)*
- **Titles** — No direct relationship. Titles don't reference chunks today. Could in future (e.g. "Surveyor of the Moors" title with `home_region` flavor). Not v4 scope. *(Agent: Titles — no action needed.)*
- **Quests** — Chunks are referenced BY quests in `explore` objectives and `expiration.chunk_id`. **Quest agent's reverse dependency is the dominant pattern here, not chunks'.** Chunks don't need to know what quests reference them. *(Agent: Quests — Agent 1 already noted.)*

### 6.3 Where chunks diverge (flavor not shareable)

- **Geographic dispatch via `geoTypes`** — UNIQUE to chunks. No other tool has a "claim this dispatch key" pattern. The geo-system → chunk-type bridge (`geo_chunk_dispatch.json` + `ChunkTemplateDatabase._auto_register_geo_types`) is chunk-architectural.
- **Template vs. instance distinction** — UNIQUE. Materials, hostiles, nodes, skills, titles, NPCs, quests all generate INSTANCES that the player encounters directly. Chunks generate TEMPLATES that the world generator rolls against. The architectural implications: longer reuse horizon, no per-instance LLM cost, immutability post-generation, no reward materialisation flow.
- **Generated wins on dispatch collision** — UNIQUE failure mode. A single bad generated chunk template that claims `geoTypes: ["forest"]` SUPPRESSES the sacred `peaceful_forest` for that geo_type. This is the "narrowing" rule in §3.2.9. Other tools don't have this — a bad generated material doesn't suppress the sacred iron_ore; it sits alongside it.

### 6.4 Recommendations to other agents

- **Nodes agent**: Accept `cross_ref_hints.spawned_in_chunk_id` in the hub input; flavor the node's narrative around its primary chunk biome ("the moors-copper seam outcrops in rust-veined cliffs").
- **Hostiles agent**: Accept `cross_ref_hints.native_chunk_ids`; flavor lore around territory.
- **Materials agent**: Ensure your tool composes cleanly under reactive cascade — when triggered by a node co-emission, your tool may not have direct geographic context. Pull region from the parent node's `cross_ref_hints` if possible.
- **NPCs agent**: When a chunk template carries `metadata.signature_feature` (proposed schema addition), NPC tool should be able to anchor an NPC's `locality_home` to that feature. Coordinate on `signature_feature` schema shape.
- **WNS / Planner+Supervisor agent**: **THE TWO LOAD-BEARING INTERVENTIONS FOR CHUNK QUALITY**:
  1. Close the `BundleToolSlice` parent_summaries leak (echoes Agent 1).
  2. Thread `bundle.directive.scope_hint.geographic_chain` through planner → hub → tool. Add `${geographic_chain}` slot to all three prompts. Chunks need this MORE than quests because chunks ARE spatial-substrate generation. Without parent biome on the input, every chunk is biome-blind.
  Also: tune `_wes_tool` body in `narrative_fragments_nl4.json` to give the weaver clearer firing guidance for `new-chunk` specifically (see §4.6).
- **WES tooling agent (cross-cutting)**: Implement reactive `hub_dependency_resolver` (memory: `hub_dependency_resolution.md`). Chunks are the highest-leverage test case — chunk → nodes → materials cascade exercises the full graph.

---

## 7. Storage / timing design

### 7.1 The generated-chunk-template pool — the core architecture

Architecture:

- **Generation event**: WNS firing emits `<WES purpose="new-chunk">` → planner (firing tier ≥3, usually 4) → hub → tool → `ChunkTemplate` JSON commits to `Definitions.JSON/Chunk-templates-generated-<ts>.JSON`. `ContentRegistry.reg_chunks` table gets a row keyed by `chunkType` with `source_bundle_id` traceback.
- **Reload**: `database_reloader.reload_for_tool('chunks')` calls `ChunkTemplateDatabase.reload()`. The dispatch bridge is rebuilt; new `geoTypes` entries are auto-registered (sacred wins on collision).
- **Visibility**: The next chunk instance generated whose `GeographicData.chunk_type` resolves to a `geoType` claimed by the new template uses that template. Already-rendered chunks DON'T regenerate.
- **No materialisation flow**: unlike quests, chunks don't need a per-instance pregen step. Templates are reusable.

### 7.2 Cadence: when do new chunks LAND on the player?

A generated chunk template lands on the player iff:
1. The player explores into virgin territory (a chunk not yet generated as an instance), AND
2. The geographic system's `GeographicData.chunk_type` for that chunk resolves to a `geoType` the new template claims, AND
3. The dispatch isn't shadowed by a sacred entry (sacred wins on collision in `_auto_register_geo_types`).

This means:
- **Player on the spawn-area frontier**: high chance of seeing new templates the next session, IF the WNS has been firing chunk-arcs along that frontier.
- **Player grinding a known region**: zero chance — they're revisiting existing chunk instances.
- **Player crossing into a brand-new region**: high chance, multiplied by how many new templates that region's geo_types map to.

**Implication for cadence**: the WNS-side cadence for `new-chunk` firings should be tuned to match the player's exploration rate, NOT raw event throughput. If the player explored 5 new chunks this session, generating 50 new chunk templates is waste. Generating 2-3 new templates aligned with the regions they're approaching is gold.

### 7.3 Orphan resolution for referenced IDs — the cascade pattern

When the chunks tool generates a template referencing `moors_copper_seam` (a node), the orphan detector at commit time will:
1. Check `registry_store.reg_nodes` for `moors_copper_seam`.
2. If present: commit.
3. If absent but same-plan upstream step produces nodes: commit (deferred resolution).
4. If absent and no upstream coverage: **block commit** — `unresolved_refs` is non-empty.

The planner is responsible for emitting upstream steps when known. The reactive resolver (memory `hub_dependency_resolution.md`, not yet implemented) handles the case where the planner DIDN'T pre-list the dep but the chunks tool generated it anyway.

**Proposed cascade flow** (when reactive resolver lands):

1. Chunks tool fires; outputs template referencing `moors_copper_seam` (new).
2. Orphan detector flags missing node ref.
3. Reactive resolver inspects the gap. Emits a synthetic `wes_tool_nodes` invocation with derived intent ("co-emit nodes content with id 'moors_copper_seam' referenced by chunk template 'dangerous_copper_moors'").
4. Nodes tool fires; outputs node referencing material `moors_copper`.
5. Orphan detector flags missing material ref.
6. Reactive resolver fires `wes_tool_materials`.
7. Materials tool fires (leaf — no upstream).
8. Recursion unwinds: materials commit, then nodes commit (now ref-valid), then chunks commit.
9. Atomic commit: all three rows land in the same transaction.

**Budget**: the reactive cascade must have a depth cap (3 is sensible — chunks → nodes → materials is the canonical max). Exceeding the cap should bail and request a planner rerun. Otherwise a chunk asking for new exotic content could balloon into a 15-step generation.

### 7.4 Adaptive context binding — does a stored template grow stale?

Less of an issue for chunks than quests because:
- Chunks don't carry "in return..." reward prose that goes stale.
- Chunks don't carry NPC dialogue voice that becomes outdated.

But chunks CAN go stale via:
- The WNS thread that birthed the chunk closes (`thread_stage:resolution`). The chunk still exists; should it stop being generated for new instances?
  - **Proposal**: NO. A closed WNS thread still leaves narrative residue in the chunk's lore. The salt moors STILL exist after the copper trade arc closes; the rust-veined cliffs are still there. The chunk template should remain available indefinitely.
- The chunk references a node or hostile whose template was later DELETED (not allowed in current architecture — generated content is append-only).
- Resource node IDs get retiered or re-balanced — `tierBias` on a template may grow inappropriate.
  - **Proposal**: pre-release, accept this. Post-release, the chunk evolution-tree work (memory: `chunk_evolution_future_idea.md`) is where retiering happens via descent.

### 7.5 What gets archived for chunks?

Less than quests. The chunk's `ContentRegistry.reg_chunks` row carries `source_bundle_id` which traces back to the firing narrative row. That's sufficient archive: "this chunk was born from bundle X which was born from NL4 narrative Y at region Z."

What's NOT archived but maybe should be:
- **First-encounter event**: when the player first walks into a chunk INSTANCE of this template. The WMS could record this as a new event type `chunk_template_first_seen`. This would close the visibility loop (§4.2) and feed back into NL4 narrative continuity ("the salt moors finally felt the player's tread"). Not v4 scope; flag as future.

---

## 8. Diversity / creativity design

User direction: *"the competition is templates that could be systematically generated... what makes a chunk feel like it BELONGS to its geographic neighbors, has narrative reason for being, rewards exploration?"*

The diversity dials for chunks, ranked by impact:

### 8.1 Region-anchoring (the biggest dial)

Every generated chunk should encode its parent region's identity in its `chunkType`, `name`, `narrative`, `geoTypes`, and at least 2 of 3-6 `metadata.tags`. A region produces a FAMILY of chunks that share narrative DNA — same dominant resource, same tier band, same controlling faction (if any), overlapping adjacency neighbors. **Implementation**: `${geographic_chain}` reaches the tool. The tool's prompt must spell out "the chunk you generate is part of a family; sibling chunks in this region share theme X and signature feature Y."

### 8.2 Biome adjacency coherence

The chunk's `adjacencyPreference` array is currently decorative (not enforced in code) but is the SCAFFOLDING for adjacency rules. The LLM should populate it with sensible neighbors:
- Same theme + same category band (`dangerous_quarry` next to `dangerous_quarry`, `dangerous_cave`).
- Same theme + adjacent category band (`peaceful_forest` next to `dangerous_forest`).
- Different theme + transition justification (`dangerous_quarry` next to `water_river` only if the chunk's narrative says "the river cuts through the cliffs").

**Proposal**: even though not currently enforced, the LLM populating these correctly TODAY gives the future adjacency-aware world generator data to read. Treat it as load-bearing for forward-compat.

### 8.3 Signature feature uniqueness

Each new chunk template should name ONE signature feature that no other template carries — the rust-veined cliffs, the standing stones, the bubbling pools, the colossal stump, the brine flats. The signature is what the player remembers. Slop has no signature. Crazy has too many.

**Implementation**: tool prompt rule — "your `metadata.narrative` MUST name a signature feature in the first sentence. The signature should not duplicate any feature in `recent_registry_entries`."

### 8.4 Resource density signature

One resource at `very_high`, 1-2 at `high`/`moderate`, 1-2 at `low` accents. Three slot-machine resources at `moderate` makes a mush. The signature resource is the "this is the X biome" identity.

**Implementation**: tool prompt rule on the density spread distribution; hub prompt rule on `cross_ref_hints.primary_resource_ids` listing the signature first.

### 8.5 Enemy spawn signature

One signature antagonist at `high` or `very_high` density (the copperlash rider in the moors, the void wraith in the paradox hollow, the worldtree wisp in the ancient grove). Supporting wildlife at moderate/low. Empty enemySpawns is acceptable for peaceful and water chunks.

### 8.6 Tier-band variance

A region should produce a SPREAD of chunks across tier bands, not all the same. The `peaceful_forest` (tier 1) feeds into `dangerous_forest` (tier 2) feeds into `rare_forest` (tier 3-4). Sacred file is correctly tiered; generated chunks should respect the region's expected tier_anchor but vary ±1 around it.

**Implementation**: hub prompt rule — when emitting multiple specs in one batch, vary their `hard_constraints.tier_anchor` to create a tier spread.

### 8.7 Faction territoriality

When the WNS thread that fired the directive names a faction (e.g. "the copperlash riders"), the chunk should encode that faction:
- Via `metadata.tags` including `faction-territory:moors_raiders` (if NEW: tag allowed) or via narrative naming.
- Via `enemySpawns` including the faction's known hostiles.
- Via future `metadata.controlling_faction` field (proposed schema gap).

### 8.8 Water-chunk subtype variety

Sacred file has `water_lake`, `water_river`, `water_cursed_swamp`. Variety axis: `tilePattern` shape (coverage, islands, toxicity, bridges, riverWidth). The LLM should generate water chunks with novel tilePattern combinations:
- A tidal pool chunk (water_coverage=0.3, isToxic=false, hasIslands=true with seasonally-varying shore).
- A salt marsh chunk (water_coverage=0.5, isBrineRich=true — would be a NEW: tilePattern key).
- A geyser-field chunk (water_coverage=0.4, isToxic=false, hasHotSprings=true).

This is genuinely new biome design space. Designer review on tilePattern key additions.

### 8.9 Emergent proper nouns

Per memory `narrative_fragments_nl4.json`, NL4 narrative may invent proper nouns (the Standing Stones of Rust, the Worldbone Glade). When these appear in `parent_summaries` (once the leak is fixed), the chunks tool should be able to anchor `metadata.narrative` to those names. Caps: 2 per fragment, 5 per run, designer review surface.

---

## 9. Speculative future endpoints

Things the user has flagged, or that this trace surfaces as natural next-step LLM endpoints.

### 9.1 `wes_chunk_evolution_descender` — POST-RELEASE evolution tree

Per memory `chunk_evolution_future_idea.md` — DO NOT implement pre-release. The design intent:

- Chunk templates form a branching tree: `peaceful_forest → ancient_grove → primeval_wood → worldtree_glade`.
- Each rendered chunk instance has a small chance per session to evolve down its template's branch.
- Effect: world trends upward in difficulty/rarity naturally as the save ages, without explicit-instance LLM generation.

**Endpoint sketch** (post-release):
- **Trigger**: at session start, roll per-chunk-instance against `template.evolution_chance`. On success, swap the instance's template to `template.evolution_child_ids[rng]`.
- **Inputs**: existing template ID + instance position + instance age.
- **Outputs**: a NEW chunk template (one branch deeper) IF the child doesn't yet exist; otherwise the existing child ID.
- **Latency budget**: at session start, async, no player-facing latency.

**Schema room**: leave `evolution_parent_id`, `evolution_child_ids`, `evolution_chance` as optional fields in v4 schema so authoring can begin. **Do not implement the evolution roll during v4 development.**

### 9.2 `wes_chunk_signature_landmark_placer` — named-POI sub-placer

When a chunk template has a named signature feature ("the Standing Stones of Rust"), the chunk INSTANCE could benefit from a deterministic per-instance LLM call placing the landmark at a specific tile position with a specific visual (a 3x3 tile cluster of stone tiles in a triangle formation, etc.).

- **Trigger**: at chunk instance generation, IF template has `signature_feature` (proposed schema addition).
- **Inputs**: template's signature feature description + chunk's seed.
- **Outputs**: a tile-placement plan for the landmark.
- **Latency**: at chunk-load time, must be FAST or backgrounded. Probably better as a deterministic procedural placer (no LLM) — let the LLM design the SHAPE in template authoring, and procedural place it.

Endpoint count: probably folded into the chunks tool itself (extend prompt to emit `signature_feature.placement_shape`) rather than separate. Designer call.

### 9.3 `wes_chunk_ambient_designer` — weather + hazard layer

The proposed `metadata.ambient_effects` schema gap (§2.2) could justify a sub-tool for designing ambient hazards / weather:
- **Trigger**: post-template-commit, optional pass for chunks with `category: rare` or specific tags.
- **Inputs**: template + region's climate signal (does the region have a climate tag? Currently NO — see WMS-ENHANCEMENT below).
- **Outputs**: an `ambient_effects` array.

Probably premature for v4. Flag as future.

### 9.4 `wes_chunk_visitation_chronicler` — first-encounter narrator

Per §4.2 visibility loop gap: when the player first walks into an instance of a generated template, fire a deterministic event `chunk_template_first_seen` and optionally an LLM call to emit a 1-2 sentence WMS interpretation ("the player crossed into the rust-veined moors for the first time — the air smelled of brine and green copper").

- **Trigger**: per chunk template, on first instance encounter by player.
- **Inputs**: template's narrative + the moment context (game time, player's recent activity).
- **Outputs**: 1-2 sentences + tags, written to WMS as an L2 interpretation.
- **Where it lives**: probably WMS-side (it's chronicler-voice, fits the substrate). Could be a new evaluator (extending `exploration_regional.py`) rather than a new endpoint.

Endpoint count: probably +0 — folded into an existing WMS evaluator.

### 9.5 `wes_chunk_geo_dispatch_curator` — geo_type collision resolver

When a generated chunk template's `geoTypes` collides with a sacred entry, today's behavior is "sacred wins." But sometimes the designer WANTS the new template to win (overriding a placeholder sacred). A curator endpoint could:
- **Trigger**: at commit time when collision detected.
- **Inputs**: existing sacred mapping + new template's claim + designer policy.
- **Outputs**: a routing decision per collision (keep sacred / replace with generated / narrow generated to a new key).

Could be folded into the supervisor pass rather than a standalone endpoint. Designer call.

### 9.6 Speculative future schema additions to draft NOW (no endpoint)

These don't need endpoints but should be tracked:
- `signature_feature` (§2.2) — structured field.
- `wns_thread_id` — narrative-thread linkage.
- `tier_anchor` — explicit top-level tier.
- `controlling_faction` — territoriality.
- `evolution_parent_id` / `evolution_child_ids` / `evolution_chance` — post-release evolution tree slots.
- `ambient_effects` — hazard layer.

### 9.7 Big-picture: the 2-endpoint chunks pipeline grows to potentially 3-4

Current: `wes_tool_chunks` + `wes_hub_chunks` (2).
With speculatives: + `wes_chunk_evolution_descender` (post-release) + `wes_chunk_visitation_chronicler` (probably WMS evaluator) + `wes_chunk_signature_landmark_placer` (probably folded into chunks tool) (potentially 3-5 total over time).

Pragmatic v4 count: **2 endpoints — the load-bearing minimum**. Post-release: +1 for evolution. The two shipped now are the load-bearing minimum and the runtime is fully wired for them. **Chunks are the readiest tool. The work is prompt furnishing, not plumbing.**

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Thread `bundle.directive.scope_hint.geographic_chain` through planner → hub → tool.** Add `${geographic_chain}` slot to all three prompts. Chunks need this MORE than quests because chunks ARE spatial-substrate generation. Without parent biome on the input, every chunk is biome-blind. Single fix, three places.
2. **Close the `BundleToolSlice.parent_summaries` leak** (echoes Agent 1). Without parent narrative the chunks tool generates from `directive_text` alone — and the directive_text is a 1-2 sentence body, not the rich regional arc that birthed it.
3. **Add the `geoTypes` collision-avoidance rule to the chunks tool prompt.** Currently a generated template can silently SUPPRESS a sacred biome by claiming a sacred dispatch key. The tool should be biased toward narrower regional keys (`salt_moors_quarry`, not `quarry`).

Everything else in this trace — reactive cascade resolution, signature feature schema additions, evolution-tree post-release work, ambient hazards — is downstream of these three.

**The pipe is wired. The world the pipe ships is the work that remains.**
