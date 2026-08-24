# Feature Trace 04 — Materials

**Wave:** 2 (parallel)
**Owned endpoints:** `wes_tool_materials`, `wes_hub_materials`
**Final output artifact:** A single `Material JSON` row in `items.JSON/items-materials-generated-<timestamp>.JSON` matching the shape of `items-materials-1.JSON` (sacred reference). Loaded by `MaterialDatabase` into `MaterialDefinition` dataclass. Surfaces in inventory tooltips, crafting input lists, recipe ingredient panels, and loot drops.
**Date:** 2026-05-26

> "What makes a material feel like it BELONGS to its source? This herb only grows in this swamp; this ore only forms in this volcanic chunk; this pelt only drops from this enemy species."

This trace is anchored on a player who looted a wolf in the moors and now sees an unfamiliar word in their inventory: *Moors Copper Ore*. The hover tooltip is the entire UX. The entire pipeline exists to make that hover read like a thing that exists in a world rather than a number with an icon.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

There is no "scroll unfurl" for materials. There is no in-world voice. The player kills a wolf, opens their inventory (or hovers an item stack), and sees:

```
Moors Copper Ore   x3
Tier 2  •  Uncommon  •  Metal
"A pitted red-green ore dragged from fog-wrapped cliffs on the
windward moors. Salt-etched veins run through it, and smiths say
the resulting ingots sing thinly when struck."
```

That tooltip is the entire delivery surface for a material. Everything else — the icon, the stack count, the color-coded rarity band — is determined by code, not the LLM. The LLM authors **the name and the narrative line**, and (less visibly but more loadbearing) **the category, tier, rarity, and tags** that decide every downstream behavior.

The other surfaces where the player encounters this material:
- **Crafting menu input list** — when a recipe demands "3 Moors Copper Ore," the player must recognize what they have. Name discipline matters more than narrative here.
- **Loot drop popups** — the brief flash that says "+1 Moors Copper Ore" when the wolf-kill or node-mine completes. Read-time: half a second. Name only.
- **Resource node interaction prompts** — when a node names itself as "a Moors Copper Seam," the player reads the node card. The material name must match. Cross-feature: §6.
- **Recipe books / encyclopedia** — discovery surfaces that show the material in its discipline context.

So the material's player-facing footprint is:
- ~80% the name (read constantly, briefly).
- ~15% the narrative line (read once on hover, occasionally referenced).
- ~5% the explicit tier/rarity/category labels (read by power-users planning crafts).

The narrative is the part the LLM can most spectacularly add value to. The name is the part the LLM can most spectacularly ruin.

### 1.2 Timing budget — the architectural constraint

Materials are pure cascade-time content. There is no scroll-open analogue, no "open dialogue with NPC" trigger, no UI affordance that fires LLM inference at material consumption. By the time the player loots their first lump of `moors_copper_ore`, the JSON has been on disk and in `MaterialDatabase` for hours of play. Refer to memory `living_world_wns_wes_v4_implementation.md`: WES is cascade-time only.

This dictates:
- The `wes_tool_materials` call MUST fire during cascade time alongside the `wes_execution_planner`'s plan execution.
- Generated material JSONs land on disk as `items.JSON/items-materials-generated-<timestamp>.JSON` (sacred file naming convention), commit to `ContentRegistry.reg_materials`, and reload `MaterialDatabase` so the new material is queryable everywhere it must be (crafting, drops, gather).
- **There is no in-line generation moment.** The player never waits for a material to render. The latency budget is therefore the cascade's latency budget (5-20s for a multi-step plan), not the material's individual latency.
- The "personal shopper" question collapses for materials: we don't need to know the player's level when we generate one. A material's *price* in the economy might scale to player level later, but the JSON shape is fixed at cascade-time.

What this gives us in exchange: **freedom to write longer, denser, more region-bound narrative.** A material's narrative line doesn't have to fit a 2-second read window — it has to be hover-worthy, which is generous. We can afford 2-3 sentences. We can afford to name the cliff face and the bird that nests there.

### 1.3 Failure modes — what BAD looks like

Three flavors, same taxonomy as Agent 1's quest trace, translated to materials:

**(a) Slop.** *Iron Ore II. Tier 2. A common ore.* The name is procedurally counter-1'd. The narrative reads like ad copy for a fantasy commodity. There is nothing in the text that ties the material to its origin chunk, the wolf that dropped it, the moor it was gathered from. The player loots ten of these in a session and remembers none of them. *(Defense: thread the firing-address biome + parent chunk theme + the WNS thread that birthed this material through the prompt's narrative slot. If the material can't reference its mountain or its monster, the leak is somewhere on the WNS→WES seam.)*

**(b) Stagnant predictability.** Every region adds another copper variant. Every wolf species drops "wolf pelt" with the species name appended. The material taxonomy bloats but every entry is a near-duplicate of an existing one. The player understands the game's vocabulary as *"every chunk gets one new ore, you can guess the name."* *(Defense: cross-categorical generation. Materials should sometimes be herbs, gels, scales, bones, salts, oils, threads, dusts — not just ore-variant N. The hub prompt must rotate categories; the recent_registry_entries query must reveal recent category histograms.)*

**(c) Craziness.** The LLM, given creative liberty, generates `Time-Soured Vapor` (T4 legendary, category: temporal). The narrative invents a scholarly faction (the Chronomorphs) that doesn't exist, sets the source as the Bones-of-the-Hours mountain (no such chunk), and tags it `["NEW:phosphorescent", "NEW:future_resonance"]`. The material is unforgettable and orphaned — no recipe consumes it, no node yields it, no drop table lists it. *(Defense: category allow-list, rarity allow-list, tag allow-list with `NEW:` prefix discipline, cross-ref discipline at the hub layer enforcing the planner's depends_on graph. A material spec without a co-emitted node or hostile to source it is a planner-level mistake the hub-dep-resolver should catch.)*

**(d) Orphan-from-the-world.** A subtle failure: the material is well-named, well-categorized, well-tagged — but no node yields it, no hostile drops it, and no recipe consumes it. The material exists in the database forever, never enters inventory, has no UX footprint. This is what happens when the planner emits a `materials` step without co-emitting at least one of {node, hostile_drop_attachment, recipe_attachment}. The orphan detector currently catches FORWARD orphans (this material refers to something missing); it doesn't catch BACKWARD orphans (nothing in the world refers to this material). *(Defense: post-commit reverse-orphan check OR planner rule: every `materials` step must depend on or be depended-on by at least one of [nodes, hostiles, recipes]. Currently NOT enforced — see §4.6.)*

### 1.4 What "good" actually looks like

A good generated material, in the player's words after playing for an hour: *"The copper they use in the moors is different from anywhere else — the smiths there get a thin singing tone when they strike it. I remember because I had to gather a stack of it for the captain's commission."*

Three properties:
- **Place-bound** — the player can name the chunk / biome / source the material comes from.
- **Sensorially distinct** — the narrative gives a hook that's not just "it's metal" (color, sound, smell, behavior under heat, who prizes it).
- **Useful** — the material slots into at least one recipe, drops from at least one source, and the player has reason to gather it.

The third property is "infrastructure" rather than narrative — but if the LLM produces material JSON whose tags don't match what existing recipes consume, the material is useful only after a recipe gets generated too, and the cascade has to coordinate that. See §7.3 on co-emission economics.

---

## 2. Output artifact schema completeness audit

The `MaterialDefinition` dataclass is locked in `data/models/materials.py`. The on-disk JSON shape (per `items-materials-1.JSON`) maps to it with auto-generated icon paths and a default `max_stack`. Every field below must be filled by either `wes_tool_materials` or the loader. The "Author" column names which.

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `materialId` | str (snake_case) | `wes_tool_materials` | Should encode region + descriptor. `moors_copper_ore` beats `mat_142`. Must be unique against registry (orphan detector checks this). 2-4 words. |
| `name` | str (Title Case) | `wes_tool_materials` | Reads aloud well, doesn't collide with existing names, evokes the source. "Moors Copper Ore" beats "Copper II." |
| `tier` | int 1-4 | `wes_tool_materials` | Drives crafting difficulty point value (T1=1, T2=2, T3=3, T4=4 — `difficulty_calculator.py:36-40`), tier multiplier (T1=1.0x, T2=2.0x, T3=4.0x, T4=8.0x, immutable per CLAUDE.md), and rarity pairing. Must match the planner's slot tier. |
| `category` | str (allow-list of 5) | `wes_tool_materials` | One of [metal, wood, stone, elemental, monster_drop] per existing sacred file. **NOTE: tool prompt says 5 categories, hub prompt says different 5 ([ore, wood, fish, herb, stone]) — see §2.1.** |
| `rarity` | str (allow-list of 5) | `wes_tool_materials` | One of [common, uncommon, rare, epic, legendary]. Tier-rarity pairing rule: T1→common/uncommon, T2→common/uncommon, T3→rare/epic, T4→epic/legendary. |
| `description` | str | (loader/optional) | Often empty; the narrative carries the prose load. Schema allows it but most existing materials leave it blank. |
| `maxStack` | int | (defaults to 99) | Designer-controlled stack cap. Tool need not set it. |
| `properties` | Dict | `wes_tool_materials` (optional) | Bool/numeric flags. Existing materials use it sparsely (acid_resistant, malleable, etc.). Material-category-driven. |
| `iconPath` | str | (auto-generated by loader from materialId) | Loader generates `materials/<materialId>.png` if absent. **Real risk: PNG doesn't exist — see §2.1.** |
| `flags.placeable` | bool | (typically false for raw materials) | Only for devices/turrets/tools. Raw materials = false. |
| `type` / `subtype` / `effect` | str | (typically empty for raw materials) | Only for devices/consumables. Raw materials leave blank. |
| `metadata.narrative` | str (2-3 sentences) | `wes_tool_materials` | The hover-text load-bearing field. Place-bound, sensorially distinct, ideally tied to source (chunk biome, monster species, region arc). |
| `metadata.tags[]` | List[str] (2-5 from allow-list) | `wes_tool_materials` | The functional spine. Tags drive: CNN classifier input (smithing/adornments), stat_tracker categorization (gathering/loot), UI filtering (encyclopedia, search), discipline routing (alchemy reagents vs smithing inputs). Per memory `tag_system_functionality.md`: silent acceptance of novel tags = silent functionality loss. |

### 2.1 Schema completeness — what's MISSING / INCONSISTENT

This is a `[WES-SCHEMA-GAP]` audit. Reading the current code against the sacred reference JSON:

- `[WES-SCHEMA-GAP]` **Category allow-list mismatch between hub and tool prompts.** The current hub prompt (`prompt_fragments_hub_materials.json:_core.system`) says categories are `[ore, wood, fish, herb, stone]`. The current tool prompt (`prompt_fragments_tool_materials.json:_core.system`) says categories are `[metal, wood, stone, elemental, monster_drop]`. The sacred file `items-materials-1.JSON:metadata.categories` declares `[metal, wood, stone, elemental, monster_drop]`. **The hub will instruct the tool to pick "herb" or "fish"; the tool's prompt forbids it and will reject; orphan detector won't catch a category mismatch.** This is the single most concrete prompt-furnishing bug in the materials pipeline.
  - Fix: reconcile both prompts and the sacred file to one canonical set. Recommend expanding sacred categories to `[ore, ingot, plank, wood, stone, gem, herb, fish, pelt, bone, gel, essence, monster_drop]` (or similar) — the existing JSON already implicitly contains many sub-categories shoehorned into the 5 official ones (e.g. `wolf_pelt` is currently `monster_drop` not `pelt`). Designer call: expand or unify down.
- `[WES-SCHEMA-GAP]` **No `source_attribution` field.** The material JSON does not record WHICH chunk template / hostile species / resource node birthed it (forward link only; the node's `drops` list points TO the material, not vice-versa). A material has no idea where it came from. This matters for:
  - The hub-dependency-resolver (memory `hub_dependency_resolution.md`) wanting to fan out from a missing chunk material to find existing referrers.
  - The reverse-orphan check (a material with no referrers in the world is dead weight — §1.3.d).
  - The WNS chronicler weaving "the moors copper" into NL4 narrative — it currently can't query "which materials come from the moors" without joining through node and hostile tables.
  - Recommend: optional `metadata.source_chunks: [chunk_template_id]` + `metadata.source_hostiles: [hostile_id]` + `metadata.source_nodes: [resource_node_id]` fields, set by the planner's depends_on graph at commit time. This is *cross-ref glue* that the registry should populate; the tool need not emit it.
- `[WES-SCHEMA-GAP]` **No `gather_quest_id` reverse cross-ref.** Per Agent 1's seed note, the material tool should accept `cross_ref_hints.gather_quest_id` so that a material born to satisfy a quest's gather objective can flavor itself around that quest. Currently the hub prompt's `CROSS_REF_HINTS shape` lists only `{derived_from: <material_id>}` (alloys, future). Add `gather_quest_id`, `dropped_by_hostile_id`, `yielded_by_node_id`, `crafted_via_recipe_id`. The tool then weaves these into the narrative.
- `[WES-SCHEMA-GAP]` **No `economy_band` or value attribution.** A material has no in-game "base price." The existing materials in `items-materials-1.JSON` carry no economy field, but the difficulty calculator uses tier as a proxy for cost. For player-economy work (vendors, auction, trade routes), a material needs a band. Punt this — but flag that future quest reward materialization (Agent 1's `wes_quest_reward_pregen`) may want a material-economy signal when filling `rewards.items[]`.
- `[WES-SCHEMA-GAP]` **No `discipline_affinity[]` field.** The CLAUDE.md guidance lists 6 crafting disciplines (Smithing, Alchemy, Refining, Engineering, Enchanting, Fishing). A material implicitly belongs to one or more (copper_ore → smithing/refining; oak_log → smithing/engineering/refining; wolf_pelt → smithing-armor/refining/alchemy). Currently this is encoded only through which recipes consume the material. If a material is generated WITHOUT a co-emitted recipe (which the WES system today cannot generate — see §6.4 on the missing recipes tool), the material's discipline affinity is invisible. Add a `metadata.discipline_affinity: [smithing, alchemy, ...]` list so future recipe generation OR human authoring can match.
- `[WES-SCHEMA-GAP]` **No `seasonal_availability` or `time_envelope` binding.** Materials in living worlds sometimes ebb (fish run in spring, certain herbs only bloom in summer fragments). The existing schema doesn't carry it. Optional future field.
- `[FRAGMENT-GAP]` **Hub prompt lacks `recent_registry_entries.by_category` histogram.** The hub gets `recent_registry_entries` as a flat list (per `BundleToolSlice.recent_registry_entries`). To enforce category rotation (defense against §1.3.b), the hub needs a count-by-category. Currently the planner/orchestrator passes a flat list and the hub must derive it itself — fragile. Add `recent_registry_entries.histogram_by_category` as a pre-computed dict.
- `[FRAGMENT-GAP]` **Tool prompt's tag allow-list is alphabetized but lacks tag-group structure.** The current `TAG ALLOW-LIST` in the tool prompt is one flat alphabetized list of ~60 tags ("advanced, air, ancient, basic, blood, carapace..."). The materials tagging in `items-materials-1.JSON` actually carries 3-axis tag patterns: a *quality axis* (basic/refined/fine/standard/advanced/legendary), an *origin axis* (metal/wood/stone/elemental/monster), and a *property axis* (durable/sharp/magical/temporal/etc.). The flat allow-list doesn't communicate that the tool should pick approximately one tag per axis. Add tag-axis structure to the prompt.

### 2.2 Pipeline link audit (per memory `feedback_tool_integration_verification.md`)

Per-link audit for `wes_tool_materials`:

| Link | State |
|---|---|
| 1. Prompt fragment | EXISTS (`prompt_fragments_tool_materials.json`) — but has category mismatch with hub (§2.1) |
| 2. Fixture | exists per `_meta.ledger_refs` "§1 wes_tool_materials fixture" — verify against `Game-1-modular/world_system/wes/fixtures/` at audit time |
| 3. Cross-ref schema | Hub prompt says `cross_ref_hints` is "almost always {}"; tool prompt expects it as JSON. Currently no reverse cross-refs (gather_quest_id, etc.) — §2.1 gap |
| 4. ContentRegistry commit path | `reg_materials` table in `content_registry.py` (verify; line refs from `dependency_resolver.py:46` confirm presence as leaf) |
| 5. Reload target | DECLARED (`database_reloader.py:40-47`) — but `MaterialDatabase` has **NO `reload()` method**. Grep confirms `def reload` / `def _reload` are absent from `material_db.py`. **Reload silently degrades.** Per memory note: "reload methods exist only for chunks/npcs/quests today (others silently degrade)." Materials are on the "silently degrade" list. |
| 6. Reload method on database singleton | MISSING (see link 5) |
| 7. Game consume path | `MaterialDatabase.get_instance().get_material(id)` is read everywhere (inventory, crafting, drops, gather). If the database isn't reloaded post-commit, newly-generated materials are invisible to the runtime until the next process start. |
| 8. E2E test | Test exists for the reloader's plumbing (`test_database_reloader.py`) but it MONKEY-PATCHES the reload target to a dummy — it doesn't test the actual `MaterialDatabase` round-trip with a generated material. **Real-world reload is untested.** |
| 9. Designer Ledger flag | Materials reload is a known silent-degrade per memory; should be in `DESIGNER_LEDGER.md` |

The **load-bearing fix for the materials pipeline** is implementing `MaterialDatabase.reload()`. Without it, every cascade-generated material lives only in `reg_materials` and the next-spawn world is none the wiser. (Inventory, recipes, drops, all silent.)

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a 1990s slot-machine material generator emits, given a tier + category slot:

```json
{
  "materialId": "iron_ore_2",
  "name": "Iron Ore II",
  "tier": 2,
  "rarity": "uncommon",
  "category": "metal",
  "metadata": {
    "narrative": "An uncommon tier 2 metal ore.",
    "tags": ["metal", "uncommon"]
  }
}
```

This is fine. This is what every prior version of this game has shipped. It is also exactly what the player has seen in every prior crafting RPG. The narrative has zero hooks; the name reads like a column header in a spreadsheet; the tags are tier+category restated. The player will gather it because the crafting recipe demands it, then forget it.

### 3.2 What we have to add to exceed this

Field-by-field, what the LLM must contribute:

1. **`materialId`** — encode region + descriptor. `moors_copper_ore` instead of `iron_ore_2`. Needs the firing address's locality/region/biome name in `address_hint` plus a descriptor pulled from the prose_fragment or thematic_anchors.
2. **`name`** — Title Case match of the materialId; "Moors Copper Ore." Reads cleanly in inventory popups.
3. **`tier`** — set by the planner via `hard_constraints.tier`. Tool obeys. No invention.
4. **`category`** — set by the planner; tool picks from allow-list. The diversity is in WHAT the planner asks for, not WHAT the tool decides.
5. **`rarity`** — tier-rarity pairing rule. A T2 should rarely be epic; a T1 should never be legendary. Set by planner's slot OR derived by tool from tier.
6. **`metadata.narrative`** — THE field. 2-3 sentences. The LLM has to:
   - Name the source surface (cliff, vein, swamp, beach, deep cave, kelp bed).
   - Give a sensory detail that isn't generic (color, sound when struck, smell when worked, behavior under heat, ritual use).
   - Tie to the broader region the WNS thread is about (if the moors are in copper-trade restructuring, this copper carries that weight).
   - Optionally, name who prizes it (the smiths of the moors, the alchemists of the riverlands, the wraiths of the deep).
7. **`metadata.tags`** — 2-5 from allow-list. The functional spine — tags drive CNN classifier input (smithing materials are CNN-classified at recipe-grid time), stat_tracker (gathering events tagged by material), UI search/filter. Cross-axis (quality + origin + property) selection.

The delta is: **place-bound name, sensorially distinct narrative, axis-rotated tags.** Everything in the pipeline must serve these three properties.

---

## 4. Backward trace through the pipeline

Rung-by-rung walk from "player hovers material in inventory" back to "WMS event row." Each rung names what it consumes, what it emits, what could leak.

### 4.1 Rung 0 — Player hovers material in inventory (player-facing)

Consumes: `MaterialDefinition` from `MaterialDatabase`. Loader resolves the `iconPath` (auto-generates if missing — note that auto-generated icons point to PNG files that **don't exist for generated materials**; the inventory will render a fallback or broken-image icon).
Emits: hover tooltip + crafting recipe lookups + drop popup names.
Risk: if `MaterialDatabase.reload()` doesn't actually exist (it doesn't — §2.2 link 6), the just-cascaded material is INVISIBLE here. The player loots a wolf, the drop log says "+1 Moors Copper Ore" only if the loot table was reloaded too — currently it isn't, because the hostile drop reference is keyed by string `materialId` and the hostile loader has its own reload path.

### 4.2 Rung 1 — Game-runtime consumers

Consumers, in order of impact:
- `Character.inventory.add(material_id, qty)` — adds to inventory by string ID. The material must exist in `MaterialDatabase` for the tooltip to populate. Otherwise an unknown material slot.
- `RecipeDatabase` — recipes reference material IDs as inputs. New generated materials with no recipe path are unused.
- `Resource node `drops[]`` — yields the material at gather time.
- `Hostile `drops[]`` — drops the material at kill time.
- `CraftingClassifier` (CNN/LightGBM) — for smithing/adornments, the CNN reads the material's image grid + tags as input. New materials joining a recipe must have classifier coverage; currently the CNN is pre-trained against the existing material taxonomy. **A novel material whose visual icon doesn't exist can't be CNN-classified into a recipe — invented-items system breaks.** [WES-SCHEMA-GAP] flagged in §2.2 link 5/6 territory.
- `StatTracker.record_resource_gathered(material_id, quantity, location)` — fires on every gather. The material ID is recorded; if material doesn't resolve in `MaterialDatabase`, the gather record carries a phantom ID. (Recoverable from logs; not catastrophic.)

There is no LLM at this rung. Materials are pure-data.

### 4.3 Rung 2 — `wes_tool_materials` (one ExecutorSpec → one material JSON)

Inputs (from `prompt_fragments_tool_materials.json:user_template`):
- `spec_id`, `plan_step_id`, `item_intent`, `hard_constraints` (JSON: tier/biome/category/rarity), `flavor_hints` (JSON: name_hint, prose_fragment, properties, thematic_anchors), `cross_ref_hints` (JSON: derived_from for alloys; rest TBD per §2.1).

Output: one material JSON per spec.

What's MISSING:

- `[WES-SCHEMA-GAP]` **The bundle's narrative context at the tool layer.** Same `BundleToolSlice.parent_summaries` leak Agent 1 flagged. The tool sees `item_intent` (one sentence) and `flavor_hints.prose_fragment` (one phrase). The WNS NL4 narrative that spawned the directive — the prose paragraph naming the moors-stone, the copperlash riders, the salt-tax — never reaches the tool. The narrative line the tool writes has only `item_intent` + `prose_fragment` as anchors.
  - Concrete impact: if the planner step's intent is "rust-veined copper variant for the moors" and `prose_fragment` is "salt-pitted, holds acid," the tool will write 2-3 sentences about salt-pitted copper. It will NOT mention the moors-stone road, the copperlash riders, or the salt-tax — because the tool never sees that paragraph. The narrative becomes generic geology.
  - Fix: extend tool's user_template with `${narrative_excerpt}` slot; have hub thread it through via `flavor_hints.narrative_excerpt` (or pass parent_summaries through the slice).
- `[WES-SCHEMA-GAP]` **The co-emitted node / hostile that will source this material isn't in the tool's view.** When the plan is `[materials → nodes → hostiles]` and the tool is generating materials FIRST, the tool doesn't yet know which hostile will drop it. The narrative has to be source-aware OR the planner must run materials AFTER its dependents — neither is the case today. Two fixes:
  - (a) Run materials last in the DAG order with placeholder IDs in earlier steps; resolve forward-refs at commit. Complex.
  - (b) Planner emits descriptive slots in the materials step: `slots: {dropped_by_hostile_role: "raider", yielded_by_node_terrain: "cliff"}` even when those IDs don't yet exist. Cheap.
  - Recommend (b) — slot semantics, not ID semantics.
- `[FRAGMENT-GAP]` **The recent material registry's category histogram.** §2.1 gap also surfaces at the tool layer: tool should see what categories are over-represented and bias away from them.
- `[FRAGMENT-GAP]` **Tag library doesn't communicate axis structure** — §2.1 again.
- `[FRAGMENT-GAP]` **The tag library in the prompt is hand-maintained, not pulled from `Definitions.JSON/tag-definitions.JSON`.** The tool prompt lists ~60 tags in its allow-list, but the canonical tag definitions live in `tag-definitions.JSON`. Memory note: "prompts are 'growing prompts.'" The current prompt-fragments allow-list will drift from the canonical file as designers add tags. Fix: a build step that regenerates the tool prompt's allow-list from the canonical file, OR a runtime substitution `${tag_library_material_safe}`.

### 4.4 Rung 3 — `wes_hub_materials` (one plan step → batch of ExecutorSpecs)

Inputs (from `prompt_fragments_hub_materials.json:user_template`):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: takes a plan step like "three herbs for the salt marshes" and emits N specs, each fully-loaded with hard_constraints + flavor_hints + cross_ref_hints.

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same `BundleToolSlice.parent_summaries` leak as the tool.** The hub gets a slice via `slice_bundle_for_tool`, which already strips `parent_summaries`, `firing_layer_summary`, the WMS events delta. Fix at this layer benefits the tool. Reference: Agent 1's §4.4.
- `[WES-SCHEMA-GAP]` **Category allow-list mismatch with tool (§2.1).** Critical — fixing this is a 10-minute prompt edit but every untouched cascade has been silently producing wrong categories. Hub's `[ore, wood, fish, herb, stone]` is a richer taxonomy than the tool/sacred `[metal, wood, stone, elemental, monster_drop]`. The current pipeline either (a) the tool is silently re-categorizing whatever the hub specifies (so "herb" hub becomes "elemental" tool — wrong) or (b) the tool rejects on mismatch (so hub "herb" specs fail). Either way is broken. Reconcile.
- `[FRAGMENT-GAP]` **Hub has no biome-coherence signal.** When the address_hint is `locality:salt_moors`, the hub should know the moors biome is "salt-and-fog cliffs" and bias `flavor_hints.prose_fragment` toward salt/acid/wind imagery. Currently the hub has only the address string and the WNS-thread headlines (which may not mention biome). Add a `biome_descriptor` field assembled from the geographic registry. (Cross-feature: chunks tool / GeographicRegistry already carries this.)
- `[FRAGMENT-GAP]` **No diversity-by-tier signal in `recent_registry_entries`.** If the last 5 materials cascaded were all T2, the hub should be biased toward T1 or T3 next. Currently just a flat list.
- `[FRAGMENT-GAP]` **Co-emission awareness.** When the plan is `[materials, nodes, hostiles, chunks]` together, the hub for materials doesn't see the other co-emitted specs. So the materials' `flavor_hints` can't say "these herbs are the ones the salt-fen sprites of step s4 will guard." Cross-tool co-emission attachments would help — see Agent 1 §4.5.

### 4.5 Rung 4 — `wes_execution_planner` (one bundle → one plan DAG)

Inputs: see Agent 1 §4.6 — same prompt. The planner is the place where materials enter the plan.

Materials-specific planner concerns:

- **Materials are LEAF (in the dep graph) but rarely root (in the plan)**. Per `dependency_resolver.py:46`, materials have no upstream tool deps. But in practice the planner ONLY emits materials when something downstream needs them: a node needs a yield, a hostile needs a drop, a recipe needs an input, a quest needs a gather target. Pure-materials steps (no downstream consumer in the plan) are the §1.3.d "orphan from the world" failure.
- `[FRAGMENT-GAP]` **Planner prompt lacks reverse-orphan rule.** The prompt enumerates DAG patterns (`Material-only: [materials]`) but doesn't say WHEN a materials-only step is acceptable. A T4 region-tier firing might justify "introduce a new legendary material with no immediate consumer, because the world's lore demands the rumor of it exists" — but a T2 locality firing should never emit a materials-only step. Add a planner rule: "Materials steps without a co-emitted consumer (node/hostile/recipe/quest gather) require firing_tier ≥ 4 and the narrative directive must explicitly justify a 'rumor of' resource."
- `[FRAGMENT-GAP]` **Planner prompt's DAG templates miss material-quest binding.** The example DAG shows quest steps depending on materials (`Quest with NPC giver: [npcs] -> [hostiles or materials] -> [quests]`), but the reverse binding — a material whose narrative is flavored by the quest that gathers it — isn't expressible in the depends_on graph (would create a cycle). Resolution: material's `cross_ref_hints.gather_quest_id` is filled by the hub AT runtime when a quest step in the same plan references the material being co-emitted. Tool-level reciprocal linkage, not planner-level.

### 4.6 Rung 5 — WNS NLn weaver emits `<WES purpose="new-material">`

The `_wes_tool` fragment in `narrative_fragments_nl4.json` lists `new-material` as a region-scope bucket common at NL4: *"a region-specific resource (often paired with a new-chunk)."* NL3 (district) also lists it. NL2 (locality) does not list it commonly — which is right: a single hovel doesn't justify a new material; a region's economic restructuring does.

What's MISSING:

- `[WNS-GAP]` **`new-material` firing guidance is thin.** The NL4 `_wes_tool` example currently shows a `new-hostile`, not a `new-material`. The weaver has no exemplar for what a good material-firing directive_text body reads like. Designer task: add a worked example to the `_wes_tool` body for `new-material`. Example: *"A tier-2 herb growing only on salt-stained cliffs of the moors — used by alchemists for purging acid burns. Paired with a node spawn in moors chunks."*
- `[WNS-GAP]` **No discipline-cross-pollination signal.** A region's narrative might be about a craft (alchemy gaining prominence in the moors); the WNS should be able to fire `new-material` with discipline guidance (`<WES purpose="new-material" discipline="alchemy">a salt-blossom for purging poisons</WES>`). Currently `<WES>` is freeform body text — discipline ends up implicit in the prose. Optional attribute hardening, or just a convention in the body.
- `[WNS-GAP]` **No relationship-to-existing-material directive.** A new material might be a *cousin* of an existing one (a moors variant of common copper, an alpine variant of common iron, a swamp variant of common herb). Currently the directive_text has no slot for "the cousin of X." Recommend the WES tool accept `cross_ref_hints.related_material: <existing_material_id>` so the narrative can say "a variant of X."
- `[WNS-GAP]` **`new-material` paired with `new-chunk` is the dominant pattern but not explicitly templated.** Per the NL4 _wes_tool note "often paired with a new-chunk" — but the planner has no way to enforce this. The weaver MAY emit both `<WES purpose="new-chunk">` and `<WES purpose="new-material">` in one narrative, but they're separate buckets; the planner sees them only as separate signals. Recommend: when the planner sees both buckets in one bundle, it should default the materials' `slots.biome` to the chunks' `slots.biome`.

### 4.7 Rung 6 — WNS reads WMS L2 interpretations

The weaver consumes `${wms_context}` — 600-char rendered WMS L2 interpretations whose locality intersects the firing address. For material-relevant signals, the chain is:

- `gathering_regional.py` / `gathering_global.py` — tracks gather frequency by material_id and locality. **High gather frequency for an existing material in a locality is a signal that "this locality has a strong relationship with that material" — feeding the WNS chronicler the right voice to fire `new-material` as a variant or extension.**
- `gathering_depletion.py` — tracks node depletion patterns. **A depleted locality's materials are scarce — could spawn `new-material` directives for "the last of the [resource], the new prized."**
- `ecosystem_resource_depletion.py` — broader depletion patterns. Same.
- `crafting.py` family — tracks crafting use of materials. **High use frequency tells the chronicler which materials are economically important.**
- `combat_kills_regional_*.py` — tracks hostile kills by species. **Indirectly: a region with many copperlash kills implies copperlash drops are flowing into the economy.**
- `economy_flow.py` — tracks gold/resource flow. **Direct economy signal.**

Solid pipeline. The WMS gives the WNS the data it needs.

### 4.8 Rung 7 — WMS L2 evaluators interpret L1 events

The 33 evaluators are designer-reviewed and locked (per Agent 1). For materials, the load-bearing evaluators are:
- `gathering_*` (3 evaluators) — direct
- `crafting_*` (8 evaluators) — material consumption
- `ecosystem_resource_depletion.py` — supply/demand
- `combat_kills_*` — drop sources
- `items_inventory.py` — what materials accumulate in the player's pack
- `economy_flow.py` — trade

Material signals are well-covered at this layer. No `[WMS-GAP]` candidates surfaced.

---

## 5. Per-field provenance table

For every field the LLM authors. 9-rung WMS column applies for any tempting `[WMS-GAP]`.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `materialId` | Tool prompt | `flavor_hints.name_hint` (hub) + tool's snake_case normalization + registry-uniqueness | Yes — but uniqueness check is registry-only, not against existing sacred file | — (orphan detector handles) |
| `name` | Tool prompt | Title Case of materialId; hub's `name_hint` is the seed | Yes | — |
| `tier` | Planner → hub `hard_constraints.tier` | Planner's `step.slots.tier` | Yes | — |
| `category` | Planner → hub `hard_constraints.category` → tool prompt allow-list | Planner picks; hub specifies | Yes but with allow-list mismatch | `[WES-SCHEMA-GAP]` — see §2.1 |
| `rarity` | Planner → hub `hard_constraints.rarity` (or tool derives from tier) | Tier-pairing rule in tool prompt | Yes | — |
| `properties` | Tool prompt | Hub's `flavor_hints.properties` (optional) + tool's category-driven defaults | Yes (loose) | — |
| `metadata.narrative` | Tool prompt | The narrative slot — fed by `item_intent` + `prose_fragment` + (MISSING: parent narrative excerpt + biome descriptor) | **Partial** — same `parent_summaries` leak | `[WES-SCHEMA-GAP]` — see §4.3 |
| `metadata.tags[]` | Tool prompt | Tool's allow-list pick (3-axis structure: quality + origin + property) | Yes but allow-list is hand-maintained, not synced to canonical | `[FRAGMENT-GAP]` — see §4.3 |
| `iconPath` | Loader auto-generation | `<category-subdir>/<materialId>.png` | **DEGRADED** — PNG doesn't exist for generated materials; inventory renders fallback | `[FRAGMENT-GAP]` — production gap, not LLM gap. Asset pipeline not in scope but flag for designer. |
| `description` | Loader pass-through (typically empty) | — | Yes | — |
| `maxStack` | Loader default (99) | — | Yes | — |
| `flags.placeable` | Tool prompt (default false) | — | Yes | — |
| `type/subtype/effect` | Tool prompt (typically empty for raw materials) | — | Yes | — |
| `metadata.source_chunks` | Registry post-commit (NOT IMPLEMENTED) | Planner's depends_on graph | No | `[WES-SCHEMA-GAP]` — see §2.1 |
| `metadata.source_hostiles` | Registry post-commit (NOT IMPLEMENTED) | Same | No | Same |
| `metadata.source_nodes` | Registry post-commit (NOT IMPLEMENTED) | Same | No | Same |
| `metadata.discipline_affinity` | Tool prompt (NOT IMPLEMENTED in current allow-list) | Inferred from category | No | `[WES-SCHEMA-GAP]` — see §2.1 |
| `metadata.gather_quest_id` | Reverse cross-ref from quest tool (NOT IMPLEMENTED) | Quest tool's cross_ref_hints at commit | No | `[WES-SCHEMA-GAP]` — see §2.1 |

### 5.1 WMS-GAP walk — the one place I was tempted

Tempting candidate: **"the player's gathering behavior signature in this region"** — for the tool to flavor a new material around what the player actually gathers.

Use case: tool wants to know "is this player a heavy ore-gatherer or heavy herb-gatherer?" so a new material can lean into the player's natural play (a heavy ore-gatherer gets new ore variants; a heavy herb-gatherer gets new herbs).

I walked the 9 rungs:

1. **Direct query**: Is there a WMS event `player_is_heavy_ore_gatherer`? No.
2. **Adjacent events**: WMS L1 events of type `resource_gathered` carry material_id; querying `event_store.count_filtered(event_type='resource_gathered', material_category='metal', player_id=p)` returns ore gather count. **Yes.**
3. **Negative patterns**: Does the player IGNORE certain material categories? Same `count_filtered` query, inverse. **Yes.**
4. **Aggregation**: `gathering_global.py` evaluator already produces L2 interpretations like `gathering:ore_heavy` and `gathering:wood_heavy`. **Yes — pre-computed.**
5. **Trajectory**: Same evaluator builds severity bands (light/moderate/heavy/obsessive). **Yes.**
6. **Cross-layer climb**: NL3 / NL4 interpretations may say "the moors player is known as a metal-prospector" — this surfaces in `${wms_context}`. **Yes.**
7. **Cross-entity composition**: "Heavy gatherer + faction-affiliated with miners' guild" → "this player is a guild prospect." **Yes — composable.**
8. **Stat / ledger lookup**: `StatTracker.record_resource_gathered` writes to `StatStore`; `StatStore.get('player.gather.by_category')` returns the dict. **Yes — deterministic.**
9. **Trigger history**: Trigger manager may have fired a "heavy gatherer" trigger; query the trigger log. **Yes.**

**Verdict**: NOT a WMS gap. The signal is fully available through rungs 4 (`gathering_global.py`) and 8 (`StatStore`). The actual gap is at the **tool input layer** — the tool prompt's `user_template` carries no `${player_gathering_signature}` slot, and the hub/orchestrator doesn't assemble one. Marker: `[FRAGMENT-GAP]` on the tool prompt — but I'm NOT flagging this in this trace because **materials shouldn't be that player-aware at generation time**. Player-fit signals belong to consumption-time (quest reward materialization) where Agent 1 already flagged them; for static material JSON we want regional/world coherence dominating, with player-fit as a secondary tuning at the planner level (the planner reads player profile when deciding scope, not the material tool when authoring prose).

**Zero `[WMS-GAP]` markers in this trace.** Same as Agent 1. WMS gives us everything. Gaps are at the WNS→WES seam (bundle leak) and at the prompt assembly layer (variables not threaded through).

---

## 6. Cross-references with other features (personal shopper)

### 6.1 Heavy shared infrastructure (use as-is, no duplication)

Same shared substrate as Agent 1 (§6.1): WNS NLn weavers, WES Execution Planner, WMS L2 evaluators, tag system + tag-registry, `BundleToolSlice` (with the same `parent_summaries` leak affecting all 8 content tools), orphan detector. **Fix the slice once, benefit all 8.**

### 6.2 Material-specific shared with adjacent features

Materials are the **most cross-referenced leaf** in the dep graph. Every game-content tool refers to materials at least sometimes:

- **Hostiles** (`hostiles-1.JSON`) — every hostile has a `drops[]` list of `{materialId, quantity, chance}`. The hostile tool must reference existing materials OR co-emit them. **Reverse linkage**: material tool should accept `cross_ref_hints.dropped_by_hostile_id` and flavor narrative around the species (`wolf_pelt`'s narrative could lean into wolf species lore). [WES-SCHEMA-GAP] §2.1 covers this. *Agent assignment: Hostiles.*
- **Nodes** (`Resource-node-1.JSON`) — every resource node has a `drops[]` list of `{materialId, quantity, chance}`. Same reverse linkage as hostiles. *Agent assignment: Nodes.*
- **Chunks** — chunk templates define which nodes and hostiles spawn within them. Indirect reference to materials (chunk → node → material; chunk → hostile → material). The material doesn't need direct cross-ref to chunks, but the narrative authoring should know the chunk's biome. *Agent assignment: Chunks.*
- **Quests** — `gather` and `deliver` objectives reference material IDs in `objectives.items[].target_id`. Per Agent 1's seed note, materials should accept `cross_ref_hints.gather_quest_id`. *Agent assignment: Quests (giver of the reverse ref) + Materials (receiver).*
- **Skills** — refining/crafting skills indirectly depend on materials (a smelting skill needs an ore to consume). Tag-based linkage; no direct ID cross-ref needed.
- **NPCs** — NPCs may have material affinities ("she trades in moors copper"). No direct cross-ref in JSON schema; lives in NPC narrative prose. *Agent assignment: NPCs.*
- **Titles** — titles may grant material yield bonuses ("Salt Prospector: +10% moors copper yield"). Indirect; lives in title effect tags. *Agent assignment: Titles.*

### 6.3 Where materials diverge (flavor not shareable)

- **No reward-materialization flow.** Materials don't get materialized prose→numbers like quests do; the tool emits the final shape. No analog of `wes_quest_reward_pregen` exists or should exist.
- **No lifecycle / archive.** Once a material is committed, it lives forever. No turn-in, no expiration, no archive. (Contrast with quests, which need an ArchivedQuest table.)
- **No `wns_thread_id` linkage on the material itself.** Quests are the narrative anchor (Agent 1 §6.3); materials are downstream of quests/chunks/hostiles. A material doesn't "belong" to a thread; it's *named in* threads.
- **No dynamic context registry.** NPCs have a dynamic context registry (per memory `npc_schema_overhaul_v3.md`); materials don't need one because their JSON is fully static.

### 6.4 The recipes hole

CLAUDE.md and `prompt_fragments_wes_execution_planner.json` confirm: **there is no `recipes` tool in WES.** The 8 tools are materials/nodes/hostiles/skills/titles/chunks/npcs/quests. **Materials can be generated without a recipe path to consume them.**

This is the §1.3.d failure waiting to happen: a brand new `moors_copper_ore` exists in the database but no recipe lists it as an input. Player gathers it, can't refine it, can't smith it. It sits in inventory.

There are two possible defenses, both currently absent:

(a) **Hand-authored recipe inserts.** Designer commits to authoring recipes for any generated material. Doable but doesn't scale; the entire "limitless content" pitch breaks.

(b) **Recipe generation as a deferred tool / future endpoint.** A `wes_tool_recipes` that takes a newly-committed material and existing similar-tier recipes and produces a recipe that consumes the material. Speculative — see §9. **This is the single biggest "material orphan from the world" defense.**

Until (b) ships, the planner should DEFAULT to attaching every new material to either a node OR a hostile-drop (so it can at least be GATHERED) and accept that it may not be CRAFTABLE until a recipe lands. This is acceptable for cascade-generated content if the gather-flow alone is satisfying (gathering for its own sake). If the player is meant to USE the material, a recipe is required.

### 6.5 Recommendations to other agents

- **Hostiles agent**: When your hostile's `drops[]` references a material, declare a depends_on linkage in the planner's plan. Accept `cross_ref_hints.drops_dropped_by_hostile_id` in the material tool input so the material narrative can lean into the hostile (e.g. "torn from the spectral scales of the riverlash wraith").
- **Nodes agent**: Same pattern — when your node's `drops[]` yields a material, the material narrative should know the node's biome and terrain. Accept `cross_ref_hints.yielded_by_node_id`.
- **Chunks agent**: Materials' regional coherence depends on knowing the chunk's biome. Make sure your chunk template's biome descriptor is queryable from the geographic registry so the material hub can pull it via `address_hint`.
- **Quests agent**: Per Agent 1's seed, when a quest's `objectives.items[].target_id` references a new material in the same plan, reciprocate by setting `cross_ref_hints.gather_quest_id` on the material spec.
- **WNS / Planner+Supervisor agent**: Three asks, in priority order:
  1. **Close the `BundleToolSlice.parent_summaries` leak.** Single biggest fix.
  2. **Reconcile the category allow-list between hub and tool prompts.** Concrete, 10-minute prompt edit.
  3. **Tune the NL4 `_wes_tool` body for `new-material`.** Add a worked example; give guidance on discipline cross-pollination and "cousin of" patterns.

---

## 7. Storage / timing design

### 7.1 The generation cadence

Per the WES architecture, materials are generated:
- **At cascade-time** when a WNS firing emits `<WES purpose="new-material">` directly.
- **At cascade-time** as a co-emitted step in a larger plan (chunk + node + hostile + material).
- **At cascade-time** via hub-dependency-resolver (memory `hub_dependency_resolution.md` — not yet implemented): when another tool's output references a material ID that doesn't exist, the hub fires a materials sub-step to create it.

Materials are NOT generated:
- At inventory-hover time (zero player-facing latency tolerance for static JSON).
- At save-load time (they live in `MaterialDatabase` already).
- At craft-attempt time (the CraftingClassifier consumes pre-committed materials; novel-from-nowhere generation happens via the older `llm_item_generator.py` system for INVENTED items, which is a separate, parallel system to WES — see §9).

### 7.2 Storage layout

Two storage paths:

(a) **Sacred file**: `Game-1-modular/items.JSON/items-materials-1.JSON` — hand-authored, designer-curated, never overwritten.

(b) **Generated file**: `Game-1-modular/items.JSON/items-materials-generated-<timestamp>.JSON` — written by ContentRegistry at commit time. Loaded by `MaterialDatabase` as siblings of the sacred file. (Same pattern as `progression/npcs-generated-*.JSON` per CLAUDE.md.)

The generated file should mirror the sacred shape exactly, plus optional `metadata.source_chunks/source_hostiles/source_nodes` fields the registry post-fills (§2.1 gap).

### 7.3 Co-emission economics

When materials are co-emitted with a chunk + nodes + hostiles in one plan, the commit order matters. The dependency graph (per `dependency_resolver.py:46-56`):

```
materials (leaf)
  ← nodes (depends on material_id)
  ← hostiles (depends on drop_material_ids[])
chunks (depends on primary_resource_ids + primary_enemy_ids)
```

So commit order: materials → {nodes, hostiles} → chunks. This is the standard topological-sort the planner emits. Materials always commit FIRST in their plan, meaning their narrative is written WITHOUT knowing the eventual node/hostile/chunk names. §4.3 gap.

**Practical implication**: when the planner emits a [material, node, hostile, chunk] plan, the material's narrative will lean on the `flavor_hints.prose_fragment` and the broader narrative excerpt (once the bundle leak is fixed), NOT on the not-yet-committed downstream content. To fix this, two options:

- **Two-pass commit**: write the material with a placeholder narrative, run the rest of the plan, then re-run the material tool with full context. Doubles tool cost. Skip.
- **Slot-semantics in the planner**: have the planner annotate the material step with descriptive slots ("dropped_by_role: raider", "yielded_by_terrain: cliff") so the material tool has source-flavor without source-IDs. Cheap.

Recommend slot-semantics.

### 7.4 Reload + visibility

Per §2.2 link 5/6: **`MaterialDatabase.reload()` does not exist.** The reload target is declared in `database_reloader.py:40-47` but the method on the singleton is absent. New materials commit to `reg_materials` but the runtime's `MaterialDatabase.materials` dict doesn't see them until next process start.

**Effect on the player**: the WNS may have authored "the moors copper is a new prized commodity" hours of play before the player encounters the moors. By the time they walk in, the material may or may not be queryable. Currently the test plumbing pretends it works (test_database_reloader.py monkey-patches `_RELOAD_TARGETS`).

**Fix**: Implement `MaterialDatabase.reload()` per the pattern of `NPCDatabase.reload()` and `ChunkTemplateDatabase.reload()`. The method should:
1. Re-glob `items.JSON/items-materials-*.JSON` (sacred + generated siblings).
2. Re-call `load_from_file` for each in order (sacred first to seed; generated last to layer on top).
3. NOT clear existing entries that aren't redefined (idempotent merge — generated materials with duplicate IDs against sacred should be REJECTED at commit, not silently overwrite).

This is the **single load-bearing implementation gap** for the materials pipeline. Priority over prompt tuning.

### 7.5 No pool architecture needed

Unlike quests (which have a pre-generated pool sitting unoffered per giver NPC — Agent 1 §7.1), materials don't need a pool. The material's "offer" event is whenever a player gathers/loots, and there's no narrative scroll-open moment that demands fresh materialization. Generated materials live in the database forever, queryable instantly.

---

## 8. Diversity & creativity design

User direction (translated): the competition is materials that could be systematically generated. The benchmark is above templated baseline. The slop version is "Material #47, Tier 2, common." The stagnant version is "iron ore everywhere." The crazy version is a new material with no recipe path.

Diversity dials, ranked by impact:

### 8.1 Category rotation (HIGH impact)

The sacred file uses 5 categories: metal, wood, stone, elemental, monster_drop. Reality is richer — `items-materials-1.JSON` has wood-logs AND wood-planks; metals split into ores AND ingots; monster_drops split into pelts, gems, fangs, scales, threads, ichors, cores. The category vocabulary should expand (§2.1) to:

```
[ore, ingot, plank, log, stone, gem, herb, fish, pelt, fang, scale, ichor, gel,
 essence, thread, core, dust, salt, oil, bone]
```

The hub's `recent_registry_entries.histogram_by_category` (§2.1 gap) should drive rotation: if last 5 cascades produced 4 metals + 1 wood, bias hard toward herb/gel/essence/bone/dust.

### 8.2 Sub-category variance within a category

Within "metal," a region's metals shouldn't all be ores; they should be ores AND ingots AND alloys. Hub guidance: when a region's economy is established (tier ≥4 firing, multiple existing metals), the next material can be a refined ingot variant or an alloy.

### 8.3 Origin diversity (HIGH impact)

The narrative origin axis: gathered from a node (mining/foresting/herbalism/fishing), dropped from a hostile (combat), found in a container (loot/quest reward), or a craft byproduct (refining waste, alchemy residue). Most existing materials are origin = gathered or origin = monster-dropped. **Crafting byproducts are entirely absent from the current taxonomy.** Slag, dross, ash, salt, residue — these are materials that emerge FROM crafting failure (per `core/reward_calculator.py` quality tiers — failed crafts could yield slag as a byproduct).

Recommend: hub prompt adds a `slots.origin: [gathered, dropped, byproduct, found, traded]` axis the planner sets.

### 8.4 Property axis variance

The tag library covers properties (durable, sharp, magical, temporal, ancient, fine, etc.). When a hub asks the tool for a new T2 metal, the tool should rotate which property tag dominates. Same logic as quest objective-type rotation (Agent 1 §8.1).

### 8.5 Sensory-detail rotation in narrative

In the current sacred materials, narrative sensory hooks are limited: color/sheen ("reddish, silvery, golden-blue, dark"), heat behavior ("malleable when heated"), and rarity description. A richer rotation:

- **Visual**: color, sheen, transparency, grain
- **Auditory**: sound when struck, sound when worked, sound near magic
- **Tactile**: weight, texture, warmth/coldness, brittleness
- **Olfactory**: scent when fresh, scent when worked, scent over time
- **Behavioral under work**: response to heat, blade, acid, water, light
- **Cultural**: who prizes it, what it's used for, what stories attach

The tool prompt's narrative guidance should explicitly suggest rotating across these dimensions, NOT defaulting to color + heat-response (the existing pattern).

### 8.6 Region-specific signature

The dominant diversity dial: every region should have a recognizable material signature. The moors smell of salt and copper. The riverlands taste of mud and willow. The deep caves echo with crystal and stone. The chunks tool (Agent 8) is the natural place to declare this; the material tool reads it via `address_hint` + `biome_descriptor` (§4.4 gap).

When a region has 3+ existing materials, the next material should EXTEND the signature (a new salt-derivative for the moors) NOT diverge (a fire-elemental in the moors — wrong vibe).

### 8.7 Cousin-of-existing diversity

A new material is often a *variant* of an existing one (a moors-specific copper, a swamp-specific iron). The cross_ref_hints.related_material (§4.6 gap) gives the tool a "cousin" anchor. This is the dominant pattern in real materials science and in fantasy resource taxonomy. Recommend the hub default to cousin-of when the existing-materials-in-region pool is non-empty.

### 8.8 Quality-axis distribution

Existing materials carry quality tags: basic / standard / fine / advanced / refined / legendary / mythical. These map roughly to tier. Within a tier, the quality tag should rotate. A T2 should sometimes be `standard` and sometimes `advanced`; not always one or the other.

### 8.9 Emergent proper nouns

Same constraint as Agent 1 §8.8: 2 per fragment, 5 per run. Materials can be the carriers (`Moors Copper`, `Salt-Blossom`, `Wraithsteel`) where the proper noun is the material's name. Designer-review surface.

---

## 9. Speculative future endpoints

### 9.1 `wes_tool_recipes` — closing the loop

The single biggest hole in the WES content pipeline. Currently the planner can emit `[materials → nodes → hostiles → chunks]` but cannot emit recipes that consume the new materials. Every cascade-generated material is a recipe-less orphan.

Design sketch:
- **Trigger**: planner emits `recipes` step when a new material is co-emitted, OR hub-dependency-resolver fires it when an existing recipe references a missing input.
- **Inputs**: a material_id + existing similar-tier recipes for the discipline + the discipline's recipe schema.
- **Outputs**: a recipe JSON matching `recipes-smithing-3.json` shape (or per-discipline shape) — inputs, output, station type, station tier, performance curve.
- **Dependencies**: `materials` (the inputs) + `equipment` (the output, often) OR `materials` (the output, for refining recipes).
- **Constraint**: recipe outputs are themselves often materials (refining ore → ingot is a recipe; smithing produces equipment). The recipes tool would frequently co-emit with `equipment` (a tool that doesn't exist yet either).

Endpoint count: +1 LLM task. **Highest-priority speculative endpoint of all the 10 features' future work.** Without it, the WES "limitless content" pitch collapses for any material the player wants to USE rather than just LOOT.

### 9.2 `wes_tool_equipment` — the missing 9th tool

Related to 9.1. Currently the 8 WES tools generate raw materials, nodes, hostiles, skills, titles, chunks, NPCs, quests. **There is no tool for equipment** (weapons, armor, tools — the things crafting recipes produce). The recipe tool (9.1) implies an equipment tool that produces what the recipe outputs.

Endpoint count: +1 LLM task. Bundled with 9.1.

### 9.3 `wes_tool_material_variant` — explicit cousin-generation

Currently a "cousin of X" material is generated via the standard tool with a `flavor_hints.thematic_anchors` linkage. A specialized variant generator would:
- **Inputs**: existing material_id + locality/biome + variant axis (region / tier-shift / property-shift)
- **Outputs**: a sibling material that explicitly inherits structure from the parent.
- **Why specialize**: variants are a high-frequency pattern (every region wants a copper-variant). Specializing would give us better cross-variant consistency.

Endpoint count: +1 LLM task. Probably foldable into the main tool with a `cross_ref_hints.related_material` flag.

### 9.4 `wes_tool_material_byproduct` — failed-craft yield generation

Crafting in the current game produces only the intended output OR nothing (on extreme failure). Real metalwork produces slag; real alchemy produces residue; real refining produces dross. A byproduct tool would generate these failure-state materials.

- **Trigger**: at recipe generation (9.1) time, OR when a craft minigame's failure outcomes are designed.
- **Inputs**: recipe + failure mode.
- **Outputs**: a byproduct material + drop chance + downstream uses.

Endpoint count: +1 LLM task. Niche.

### 9.5 `wes_tool_material_lore_extension` — sustained-narrative extension

When a material has been in the game for a while AND has accumulated significant gather/use events in WMS, the chronicler may want to extend the material's narrative to reflect what the player has done with it. A T2 copper variant that the player has gathered 1000 of has earned a richer entry.

- **Trigger**: WMS evaluator notices a material's `total_gathered` or `total_used` crosses a threshold.
- **Inputs**: material JSON + WMS L2 interpretations relating to it + recent narrative threads.
- **Outputs**: extended narrative paragraph (additive to `metadata.narrative`, OR a sibling field `metadata.legend`).
- **Where it lives**: WMS-side (chronicler voice), not WES. Could be a new evaluator or a WMS L7-bound LLM task.

Endpoint count: +1 LLM task OR +1 evaluator. Probably the latter — WMS L2-L7 chronicle pipeline.

### 9.6 `wes_tool_material_relationship` — economic linkage generation

When two existing materials gain narrative significance (the moors copper rises in price; the riverlands iron falls), a relationship endpoint could generate the trade-route flavor between them — economic prose without new game state.

- **Trigger**: WNS thread tagged `narrative_domain:economic` + two referenced material IDs.
- **Outputs**: a trade-route prose fragment for WNS to consume; potentially an `<AffinityShift>` for the relevant trading-faction.

Endpoint count: +1 LLM task. Niche; foldable into the WNS chronicler's normal narrative output.

### 9.7 The bigger picture

Current materials pipeline: `wes_tool_materials` + `wes_hub_materials` (2 endpoints).

With speculatives: +5 (recipes, equipment, variant, byproduct, lore-extension; relationship folds into WNS).

Pragmatic count at maturity: **3-4 endpoints** when recipes+equipment lands (the load-bearing fix for the materials-orphan-from-world failure mode). Everything else is icing.

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Implement `MaterialDatabase.reload()`.** Without it, every cascade-generated material is invisible to the runtime until process restart. The `_RELOAD_TARGETS` plumbing is declared; the actual method on the singleton is absent. Single biggest plumbing gap.
2. **Reconcile the category allow-list between hub prompt, tool prompt, and sacred file.** Hub says `[ore, wood, fish, herb, stone]`; tool says `[metal, wood, stone, elemental, monster_drop]`; sacred file says the latter. The cascade is silently producing wrong categories or rejecting hub specs. Cheap (prompt edit), high-impact.
3. **Close the `BundleToolSlice.parent_summaries` leak (cross-cutting with Agent 1 and all 7 other tools).** Materials' narrative is currently anchored only on the one-sentence `prose_fragment` because the WNS narrative paragraph that birthed the directive doesn't reach the tool. Fix at the slice layer benefits every content tool.

The deeper hole — that no `wes_tool_recipes` exists, so every new material is potentially recipe-less and recipe-less means inventory clutter — is the **largest design gap** in the WES content pipeline. Pre-release: accept it; commit to hand-authoring recipes for cascade-generated materials, OR enforce planner rule "no new material without a gather path." Post-release: build `wes_tool_recipes` as the 9th tool (with `wes_tool_equipment` as the 10th).

Everything else in this trace — diversity dials, sub-category expansion, cousin patterns, sensory rotation — is downstream of those three fixes.
