# Feature Trace 05 — Resource Nodes

**Wave:** 2 (parallel with Materials/Hostiles/Skills/Titles/Chunks/NPCs/Bosses)
**Owned endpoints:** `wes_tool_nodes`, `wes_hub_nodes`
**Final output artifact:** `ResourceNodeDefinition` JSON row in `Definitions.JSON/Resource-node-generated-<ts>.JSON` (one per LLM call from `wes_tool_nodes`). Materialised at chunk-spawn time, not at player-encounter time. Loaded once into `ResourceNodeDatabase` singleton; instantiated as `NaturalResource` objects at chunk generation.
**Date:** 2026-05-26

> "The competition isn't no nodes. The competition is the same three trees in every forest. The benchmark is nodes that feel like they BELONG to the chunk they grow in — that the moors-stone road has copper because the copperlash riders live there, that the herb only grows where the witch lived, that the player can SEE the world's history in what's harvestable."

This trace is anchored on a player who has walked twenty paces into a new chunk and is looking at something glittering in a cliff face. Everything below exists to make that something feel like it belongs to that cliff, in that biome, in that region, in this world.

Nodes are the **silent feature**. They don't speak, don't fight, don't give quests, don't take damage in the combat sense (only the durability of pickaxe-strikes). Their narrative is entirely implicit: placement + visual + yield + name. A player will never read the `metadata.narrative` field; they only read the **consequences** of the metadata.narrative — what's there, where it is, what tool it needs, what falls out, what comes back when it respawns.

This means slop hides better in nodes than anywhere else. The slop oak tree drops oak_log, respawns "quick" (silently mapped to 60s because nobody noticed `quick` isn't in the respawn map — see §2.1), looks identical to the previous fifty oak trees. The player doesn't *complain* — they just stop exploring. We must beat that.

---

## 1. Player experience anchor + failure modes

### 1.1 The player's literal moment

The player crests a hill into a new chunk. They've never been here before. Within 5-10 paces, their eye should catch on at least one **harvestable feature** — a tree silhouetted against the skyline, a glint of ore in a cave mouth, the ripple of fish in a pool, a herb-patch on a slope. They drift toward it, equip the right tool (the game tells them if they don't have it), and start swinging. The node has HP. Three to ten swings (depending on tier) it depletes. Particles fly. Loot drops to inventory in qualitative quantities ("several oak logs," sometimes a rare crystal). Some nodes respawn in seconds; some never. The player walks on, looking for the next glint.

That is the loop. Forever. Across hundreds of hours.

The whole pipeline exists to make sure that *next* glint is different from the last, and that the last one taught the player something about THIS biome that the next one extends.

### 1.2 Timing budget — and why it differs from everything else

Quests have a 2-3 second scroll-unfurl mask. NPCs can take a beat before they speak. Nodes have **zero** masking. The player is walking, and the chunk has either already spawned the right nodes or it hasn't. Latency is not a budget concept here — nodes are baked into the chunk at chunk-instantiation time (`Chunk.__init__` → `self.spawn_resources()` → `_spawn_from_template` reads `ResourceNodeDatabase.get_instance()` synchronously). There is no live-LLM call when a player walks into a chunk.

Which means: **all node generation MUST be cascade-time work, attached to chunk-template generation**, never on-demand at chunk-load. The Request Layer can pull this off (see §7), but only because the chunk is the trigger and the nodes follow synchronously via orphan resolution. There is no scroll-unfurl-equivalent here; if the cascade hasn't finished by the time the player enters the chunk, the chunk silently spawns with whatever orphans it can resolve (default to existing nodes) and the new ones materialise next session.

This is fine. Quests need to feel fresh and personal in the moment; nodes need to feel like they've BEEN there. A node that materialises one session later is, narratively, a node the player just hadn't found yet.

User direction (per memory `hub_dependency_resolution.md`): *"hubs reactively trigger upstream tools when refs are missing; recursive through the dep graph (chunk→nodes+hostiles→materials→etc)."* Nodes sit at a load-bearing depth-2 of this graph — chunks need them, they need materials.

### 1.3 Failure modes — what BAD looks like

Three flavors, but they manifest differently than for quests.

**(a) Slop.** Every forest has oak/pine/ash. Every cave has copper/iron/tin. The biome names change, the trees don't. The chunk's `metadata.narrative` says "Windswept heath where rust-veined cliffs meet boggy flats" and the resourceDensity says `{oak_tree: high, iron_deposit: moderate}`. The narrative wrote a check the nodes can't cash. *(Defense: the chunk hub MUST co-emit biome-specific nodes through the planner DAG. The planner's example already shows this: `[materials] -> [nodes] -> [chunks]`. The failure mode is when the planner skips the node step and leans on existing sacred nodes — see §4.6.)*

**(b) Stagnant.** Nodes are placed but they're the same ones everywhere. The "rare hidden forest" of the salt marshes has the same ironwood/ebony as the rare hidden forest of the highlands. No biome ownership. *(Defense: per-region node generation, gated by the chunk template's `resourceDensity`. A chunk template generated for the moors lists `moors_copper_seam` as `very_high`, not `iron_deposit` — and `moors_copper_seam` only appears in moors templates.)*

**(c) Craziness.** The opposite failure, and for nodes the most embarrassing because it's spatial. A coral reef in a desert. A fishing pool in a cave. A tier-4 voidstone node in a starter region the player is at level 3. The LLM, given creative liberty, invents a `fossilized_reef_node` and the chunk hub eagerly drops it into a forest template because the WNS narrative mentioned "ancient seas." *(Defense: the hub's `hard_constraints.category` MUST match the chunk template's `theme`. Tool prompt enforces tool↔category matching. Chunk's `resourceDensity` is the firewall — nodes only spawn where templates allow.)*

**(d) Silent under-furnished biomes (the quiet killer).** A WES-generated chunk template references three `moors_copper_seam` nodes that the orphan resolver tried to create but the Request Layer hadn't finished by chunk-load time. Per `_spawn_from_template`:

```
# Orphan resourceIds (not in ResourceNodeDatabase) are silently
# skipped — matches the design note in
# prompt_fragments_tool_chunks.json: "A chunk that references
# orphan resourceIds silently skips them at spawn time".
```

The chunk LOOKS empty. The player walks into the rust-veined cliffs of the dangerous_copper_moors and finds nothing to harvest. The chunk template's narrative promised drama; the node spawn delivered tumbleweed. *(Defense: blocking commit on node generation BEFORE chunk template commit; or graceful fallback where the chunk's narrative degrades to "the cliffs are bare here today" so the player still has narrative shaping their expectation. See §7.3.)*

**(e) Mistier'd nodes (the gameplay killer).** The chunk says T2 but the node template was emitted as T4. Player walks in at level 8, can't break the rock with their iron pickaxe. Or worse — a T1 node sits in a T4 region, breaks instantly, ruins the sense of late-game difficulty. *(Defense: the hub's `hard_constraints.tier` MUST come from the planner step's `slots.tier`, which MUST be derived from the firing_tier's scope rules + biome danger. See §4.6 and §8.3.)*

### 1.4 What "good" actually looks like

A good generated node, in the player's mental note after playing for an hour: *"I remember when I first saw a copper seam in the rust cliffs. The salt-wind had carved a channel deep enough to rest my pick in. The miners called these honest walls — I read that in the description when I first hit one."*

Four properties:
- **Biome-rooted** — the node could only have existed in this biome. A moors copper seam is not a generic copper deposit; it has salt-wind erosion in its visual and narrative.
- **Tier-coherent** — the node's tier matches the chunk's threat level matches the player's progression band when they first encounter it.
- **Yields a material that fits the world** — the drop is either a known material that makes sense here OR a co-generated material whose narrative is consistent with the node's narrative.
- **Tool-appropriate, signal-clear** — the player knows what they need within a second of seeing it. The visual (icon + sprite) carries this; the prompt-driven narrative is the secondary signal in tooltips.

---

## 2. Output artifact schema completeness audit

The `ResourceNodeDefinition` shape is locked in `data/models/resources.py` (lines 38-77). The sacred JSON in `Definitions.JSON/Resource-node-1.JSON` is the load-bearing schema reference. Every field below must be filled by `wes_tool_nodes` (with hub-supplied constraints).

| Field | Type | Author | Quality bar beyond "schema-valid" |
|---|---|---|---|
| `resourceId` | str (snake_case) | `wes_tool_nodes` | Should encode biome + material + form. `moors_copper_seam` beats `copper_vein_2`. Must be unique against registry. Per tool prompt: `<biome>_<material>_<form>`. |
| `name` | str (Title Case) | `wes_tool_nodes` | Evokes the biome AND the harvestable feature. "Moors Copper Seam" beats "Copper Vein." Note: `<biome>` should not collapse into a regional adjective the player won't recognize ("Tarmouth Copper" requires the player to know Tarmouth). |
| `category` | str (one of [tree, ore, stone, fishing]) | `wes_tool_nodes` | Determines: tile placement (trees need land, fishing needs water), required_tool consistency, icon path. Must match the chunk template's `theme`. |
| `tier` | int 1-4 | `wes_tool_nodes` | Drives baseHealth, drop quantities, respawn behavior, AND player-fit. T1 chunks should not host T4 nodes. Sacred files enforce: T1=100hp, T2=200, T3=400, T4=800 baseHealth; the tool prompt mirrors this. |
| `requiredTool` | str (one of [axe, pickaxe, fishing_rod]) | `wes_tool_nodes` | Must match category. Tree→axe, ore/stone→pickaxe, fishing→fishing_rod. |
| `baseHealth` | int | `wes_tool_nodes` | T1=100, T2=200, T3=400, T4=800 by convention. Tool prompt allows ±20% deviation for "special cases" — undefined; likely should be tightened (see §2.1). |
| `drops[]` | list of `ResourceDrop` | `wes_tool_nodes` | 1-3 drops. Each must reference a materialId that exists OR is co-emitted in the same plan. **THIS IS THE LOAD-BEARING CROSS-REF.** Drops with orphan materialIds will fail orphan detection (in theory — see §4.4 wiring gap). |
| `drops[].materialId` | str | `wes_tool_nodes` | Material registry ref. Co-emit safe. |
| `drops[].quantity` | str (one of [few, several, many, abundant]) | `wes_tool_nodes` | Qualitative; mapped to int range in `ResourceDrop.get_quantity_range()`. T1 starter nodes skew to many/abundant (player needs volume to learn); T4 rare nodes skew to few. |
| `drops[].chance` | str (one of [guaranteed, high, moderate, low, rare, improbable]) | `wes_tool_nodes` | Primary drop usually guaranteed/high; secondary drops moderate/low; tertiary drops rare/improbable for the loot-table flavor. |
| `respawnTime` | str (one of [fast, normal, slow, very_slow] or null) | `wes_tool_nodes` | T1/T2 → fast/normal (30s/60s). T3/T4 → slow/very_slow (120s/300s). null = non-respawning, reserved for narrative one-shots. **Sacred file uses `quick` 9 times — `quick` is NOT in the respawn_map; it silently falls back to 60s ("normal"). See §2.1.** |
| `metadata.narrative` | str (2-3 sentences) | `wes_tool_nodes` | The node's appearance, location, and the sense of harvesting from it. Tooltip-visible; long-form should match the chunk's `metadata.narrative` voice. |
| `metadata.tags[]` | list (2-5) | `wes_tool_nodes` | From the allow-list. NEW: prefix required for new tags. Tags drive WMS retrieval (gathering events tagged here), tooltip categories, and visual selection (see §6). |

### 2.1 Schema completeness — what's MISSING or BROKEN

`[WES-SCHEMA-GAP]` items the audit surfaces:

- `[WES-SCHEMA-GAP]` **No `biome` field on the node itself.** A node's biome-locality is only knowable transitively through "which chunk templates reference it." If a sacred node like `oak_tree` is referenced by 12 sacred chunk templates, it lives in 12 biomes. A WES-generated `moors_copper_seam` is, by intent, biome-locked — but the node definition itself doesn't carry that constraint. Result: a future buggy chunk template can drop `moors_copper_seam` into a desert template and the orphan detector won't flag it (because the node exists). **Fix**: add optional `metadata.preferred_biomes[]` array as a soft-constraint that chunk hubs can sanity-check.

- `[WES-SCHEMA-GAP]` **No `tier_floor` on the chunk-side ref.** The chunk's `resourceDensity` carries a `tierBias` (low/mid/high/legendary) but no minimum. So a chunk template that says "this is a starter biome" can list a T4 node and the spawn pipeline will skip it (because tier_cap from the chunk's tier_range will exclude T4 nodes anyway). But the cross-ref is still valid. Result: harmless waste in the DAG — listing T4 nodes that never spawn. **Fix**: tighten the chunk hub to refuse listing nodes whose tier > chunk's max tier.

- `[WES-SCHEMA-GAP]` **No `gather_xp_curve` field.** Currently gather XP is computed from the material tier (in the gathering minigame, not the node). A T3 node yielding a T1 material gives T1 XP. This is correct from a material economics standpoint but bad from a node-progression standpoint — high-tier nodes should be "worth approaching." **Workaround**: scale xp via reward_calculator; do not add a per-node field. Acceptable as-is.

- `[WES-SCHEMA-GAP]` **No `requires_skill_unlock` field.** The "harder to harvest" nodes (mithril, voidstone) currently gate only on tool tier and node baseHealth, not on player gathering skill. A future "advanced mining" skill could unlock specific node interactions. **Acceptable as-is for v4** — defer to a future Skills tool design pass. Future cross-ref hook lives here.

- `[FRAGMENT-GAP]` **`respawnTime: "quick"` is a latent bug in the sacred file.** `ResourceNodeDefinition.get_respawn_seconds()` maps `fast/normal/slow/very_slow` — NOT `quick`. The sacred Resource-node-1.JSON uses `"quick"` 9 times (oak/pine/ash trees, copper/iron/tin/limestone/granite/shale at T1). At runtime these silently fall back to the 60s default (== "normal"). Designer impact: T1 nodes that were SUPPOSED to respawn in 30s are respawning in 60s, halving the gather rate for starter-zone players. Tool prompt #8 explicitly says "do not emit" — so generators are correct, but sacred file should be fixed. **Marker is FRAGMENT-GAP because the prompt fragment is correct; the gap is the sacred file using a value the runtime doesn't know.**

- `[WES-SCHEMA-GAP]` **The xref extractor reads `material_id` / `materialId` / `yields[]` but the schema uses `drops[].materialId`.** `_extract_node_xrefs` in `content_registry/xref_rules.py:229-253` walks: `content_json.get("material_id")`, `content_json.get("materialId")`, `content_json.get("yields", [])`. The sacred and tool-emitted schema is `drops[]` with `{materialId, quantity, chance}`. **Result**: orphan detection on node→material refs is COMPLETELY BROKEN. A node referencing a missing material will pass orphan detection silently. **This is the single most load-bearing fix for the nodes pipeline.** Fix: extend `_extract_node_xrefs` to also iterate `content_json.get("drops", [])` and emit a `REL_YIELDS` xref per drop.materialId.

- `[WES-SCHEMA-GAP]` **`SACRED_TOP_LEVEL_KEY[TOOL_NODES] = "resourceNodes"` but `ResourceNodeDatabase.load_from_file` reads `data.get('nodes', [])`.** The generated-file-writer writes the wrapper as `{"resourceNodes": [...]}` but the loader expects `{"nodes": [...]}`. **Result**: generated node files are committed to disk but loaded as 0 nodes. Tracked in xref_rules.py:538-540 ("placeholder — see PLACEHOLDER_LEDGER §17") so this IS known by the system, but it's a v4 pipeline-breaker for nodes specifically. Fix: change `SACRED_TOP_LEVEL_KEY[TOOL_NODES]` to `"nodes"` to match the actual schema.

- `[WES-SCHEMA-GAP]` **`ResourceNodeDatabase` has no `reload()` method.** `database_reloader.py:58-64` probes for `reload | _reload | reload_all`. None exist on `ResourceNodeDatabase`. The class has `load_from_file(filepath)` only, with no path resolution. **Result**: post-commit reload silently degrades — the WES-committed `Resource-node-generated-*.JSON` files are written but never reach the runtime singleton. Per memory `feedback_tool_integration_verification.md`, this is one of the 9-link verification failures. Fix: add `reload()` that walks `Definitions.JSON/Resource-node*.JSON` and merges sacred + generated, mirroring `ChunkTemplateDatabase.reload()` (which DOES work).

- `[WES-SCHEMA-GAP]` **`request_layer._ID_KEY_CANDIDATES["nodes"]` doesn't include `resourceId`.** From `world_system/wes/request_layer.py:66`: `"nodes": ("nodeId", "node_id", "resourceNodeId", "resource_node_id")`. The schema field is `resourceId`. **Result**: when the Request Layer tries to look up a staged node by content_id to mine context for a child request, it fails to find the payload. The fallback is "thin spec" with no flavor context. Fix: add `"resourceId"` to the candidates.

Combined, these five wiring gaps mean **the entire node→chunk pipeline is silently broken at the registry layer**: generated files don't reload, xref extraction doesn't catch material orphans, and the Request Layer can't enrich child requests. The fixes are all small (one-line additions/changes per file), but together they are a load-bearing block for v4 production playtest of WES-generated content.

---

## 3. Templated baseline + quality delta

### 3.1 The literal templated baseline

What a competent 1990s procedural generator (no LLM) emits, given a chunk-type and a tier-range:

```json
{
  "resourceId": "copper_node_0042",
  "name": "Copper Node",
  "category": "ore",
  "tier": 1,
  "requiredTool": "pickaxe",
  "baseHealth": 100,
  "drops": [
    {"materialId": "copper_ore", "quantity": "many", "chance": "guaranteed"}
  ],
  "respawnTime": "normal",
  "metadata": {
    "narrative": "A copper deposit. Mine it for copper ore.",
    "tags": ["ore", "metal", "starter"]
  }
}
```

This is fine. It is also exactly what we lose to. The player has seen this node a thousand times. The narrative is functional but flat. The yield is correct but lacks specificity. The name doesn't tell them where they are.

### 3.2 What we add to exceed this

Field-by-field, what the LLM must contribute beyond the slot machine:

1. **`resourceId`** — biome + material + form. `moors_copper_seam` not `copper_node_0042`. Requires `directive_text` (for intent) + `address_hint` (for biome locality) + `recent_registry_entries` (to know what's been used in this biome).
2. **`name`** — has the *taste* of the biome. "Moors Copper Seam" not "Copper Node." Requires the chunk's biome narrative + the parent NL4 fragment's tone (which the bundle slice currently leaks — see §4.4).
3. **`metadata.narrative`** — 2-3 sentences with *concrete sensory detail* and *implicit lore*. "An exposed seam of red-green copper knotted through the cliff face, where the salt-wind has carved channels deep enough to rest a pick in. Local miners call these 'honest walls' — the copper comes loose in clean shards if you work with the stone rather than against it." This requires the parent WNS narrative + the chunk's biome narrative + a sense of who lives nearby (the moors raiders, indirectly via locality NPCs).
4. **`drops[]`** — the choice of WHICH materials drop is itself flavor. A copper seam in the moors might drop primary `moors_copper`, secondary `salt_crystal` (because of erosion exposure), tertiary `rust_dust` (a curio material with crafting-niche). Slot machine drops single material per node. LLM should mix in flavor-secondaries that hint at the biome.
5. **`drops[].chance`** — slot machine uses guaranteed/high. LLM should sometimes set primary to `high` (not always guaranteed) to give the player meaningful gathering variance — sometimes you swing a copper seam and get nothing this time, and that's a *feature*, not a bug.
6. **`tags[]`** — slot machine picks 2 generic tags. LLM picks 4-5 mixing tier-appropriate tags (`starter|standard|advanced|legendary`), elemental flavor tags (`fire|ice|metal|crystal|void`), and rarity tags (`common|rare|mythical`). The combination *drives WMS retrieval* — when the WNS NL4 next fires on the moors, it'll see "the player has been gathering [ore, metal, copper, salt, starter] for weeks" and weave accordingly.

The delta is: **biome ownership, sensory texture, drop-table variety, and tag richness.** Every property serves: "did this node feel like it grew here, and not on a generic ore-spawning grid?"

---

## 4. Backward trace through the pipeline

Rung-by-rung from "player approaches the seam" backward to the WMS event row that triggered the cascade.

### 4.1 Rung 0 — Player encounters the node (player-facing)

Consumes: `NaturalResource` instance in `chunk.resources[]`, populated at `Chunk.__init__()` → `spawn_resources()` → `_spawn_from_template()` reading `ResourceNodeDatabase.get_instance().get_node(resource_id)`.
Emits: rendered node sprite, HP bar on tool-strike, particle effects, loot drops via `_generate_loot_table()` consuming `ResourceDrop.get_chance_value()` and `get_quantity_range()`.
Risk: if the chunk template references a `resourceId` that isn't in `ResourceNodeDatabase` (orphan), `_spawn_from_template` silently skips it (per design note). Result: under-furnished chunk. See §1.3.d.

### 4.2 Rung 1 — Chunk spawns nodes (synchronous, at chunk creation)

Consumes: `ChunkTemplate.resource_density` (a `Dict[resource_id, ResourceDensitySpec]`), `ResourceNodeDatabase.get_instance()`, world_generation.JSON's `resource_spawning.{peaceful|dangerous|rare}_chunks.tier_range`.
Emits: `self.resources.append(NaturalResource(pos, node_def.resource_id, node_def.tier))` for each spawn slot.
Risk: no live LLM. Either the database is loaded with the right nodes (success) or it isn't (silent skip).

**This is why node generation must be cascade-time work, not on-demand.**

### 4.3 Rung 2 — Content Registry post-commit reload (cascade tail)

Consumes: a committed `Resource-node-generated-<ts>.JSON` file (written by `generated_file_writer`).
Emits: `ResourceNodeDatabase.reload()` (DOES NOT EXIST — see §2.1) which would re-merge sacred + generated.
Risk: **the reload chain is broken for nodes** (no `reload()` method on `ResourceNodeDatabase` and `SACRED_TOP_LEVEL_KEY` mismatch). Until both wiring gaps are fixed, every WES-committed node never reaches runtime.

`[WES-SCHEMA-GAP]` markers here are the production-blocker for nodes. None of the LLM work matters until these are fixed.

### 4.4 Rung 3 — `wes_tool_nodes` (one ExecutorSpec → one node JSON)

Inputs (from prompt user_template):
- `spec_id`, `plan_step_id`, `item_intent`, `hard_constraints` (JSON: material_id REQUIRED, biome?, category?, tool_required?, tier?), `flavor_hints` (JSON: name_hint, prose_fragment, rarity, thematic_anchors), `cross_ref_hints` (JSON: material_id).

Output: one node-template JSON with the locked schema (resourceId, name, category, tier, requiredTool, baseHealth, drops[], respawnTime, metadata).

What's MISSING from the input set that the prompt should arguably have:

- `[WES-SCHEMA-GAP]` **The chunk template that will host this node.** The node tool's narrative quality is bottlenecked by NOT knowing what chunk it lives in. The hub knows (because the chunk step in the same plan named this node as a primary_resource_id), but the slice handed to the tool doesn't carry the chunk's `metadata.narrative` or `theme`. Result: the node narrative writes "rust-veined cliffs" because the prose_fragment mentioned cliffs, but if the chunk turned out to be a "swampy reach" the node feels disjointed. Fix: thread the parent chunk's narrative excerpt through the hub's `flavor_hints.parent_chunk_narrative` (or, when chunks are co-emitted in the same plan, attach the staged chunk payload via the Request Layer's context-mining path).

- `[WES-SCHEMA-GAP]` **Same `BundleToolSlice` parent_summaries leak Agent 1 flagged.** The bundle's `parent_summaries` and `firing_layer_summary` get stripped in `slice_bundle_for_tool` (context_bundle.py:342-370). For nodes, the parent narrative is *especially* load-bearing — the chunk template that spawned the node-generation step is itself born from a region-scale (NL4) WNS narrative. Without that narrative, the node's `metadata.narrative` reads as "an ore vein" instead of "the rust-veined cliff face that the copperlash riders work for tribute."

- `[FRAGMENT-GAP]` **Co-emitted material's narrative.** When the plan is `[materials] -> [nodes]` and the materials step's output isn't in the registry yet at the time the nodes hub fires, the nodes tool has no access to the material's `metadata.narrative`. Result: the node narrative can't say "the copper here has the green-blue tint that gives moors-copper its name" because it doesn't know what gave moors-copper its name. Fix: dispatcher should attach the co-emitted material's staged payload to the nodes hub input as `flavor_hints.co_emitted_material_summary`. This is the same fix as for quests (see Agent 1 §4.5), generalised.

- `[FRAGMENT-GAP]` **The chunk's `resourceDensity` weight.** When a node is co-emitted with a chunk that lists it at `very_high` density (signature resource), the tool should know this — it should be a "headline" node with strong narrative voice. When it's `very_low` (accent touch), the narrative can be sparser. Currently this density weight doesn't reach the tool. Fix: hub's `flavor_hints.density_role` = "signature" | "accent" derived from co-emit context.

- `[FRAGMENT-GAP]` **Recent WMS gathering events.** Nodes are gathered, and gathering produces WMS L1 events that aggregate into L2 interpretations (gathering_regional.py, gathering_chunks.py evaluators). When the node is being generated for a region where the player has been gathering heavily, the narrative should arguably reference this ("the cliffs here have been worked thin in recent weeks; honest walls grow scarce"). Currently NO gathering signal reaches the node tool. Walking the 9-rung WMS check (§5.1) shows the signal IS available.

### 4.5 Rung 4 — `wes_hub_nodes` (one plan step → N ExecutorSpecs)

Inputs (from prompt user_template):
- `plan_step_id`, `step_intent`, `step_slots`, `directive_text`, `address_hint`, `thread_headlines`, `recent_registry_entries`.

What the hub does: takes a plan step like "cliff-face copper seam yielding moors_copper — exposed by salt erosion along the rust cliffs" and emits 1+ `<spec>` elements with hard_constraints/flavor_hints/cross_ref_hints fully loaded.

What's MISSING:

- `[WES-SCHEMA-GAP]` **Same parent_summaries leak.** Same fix as everywhere else — the slice should preserve `parent_summaries` and `firing_layer_summary` for the hub.

- `[FRAGMENT-GAP]` **No `recent_registry_entries` filter by biome.** The hub gets *all* recent node registry entries to "avoid duplication," but the duplication that matters most is within-biome. If the moors already has 5 copper-related nodes, the hub should especially avoid emitting a 6th. The orchestrator-level wiring needs to filter `recent_registry_entries` by `metadata.tags ∩ {biome_tags}` or by `preferred_biomes[]` (once that field exists, see §2.1).

- `[FRAGMENT-GAP]` **Cross-tool co-emission awareness.** When the plan is `[materials, hostiles] -> [nodes] -> [chunks]`, the hub sees `step_slots.material_id` but doesn't see the material's *tier*, *category*, or *narrative*. So the hub fills `hard_constraints.tier` from `step.slots.tier` — but the planner picked that without seeing the material yet. Result: drift between material tier (planner-set) and node tier (planner-set), which CAN diverge from what the materials tool actually emitted. Fix: dispatcher attaches the co-emitted material's staged payload (post-materials-step) to the nodes hub input. Same pattern as quests (Agent 1 §4.5).

### 4.6 Rung 5 — `wes_execution_planner` (one bundle → one plan DAG)

The planner has nodes listed as a tool. Per the planner prompt's "DEPENDENCY PATTERNS":

```
Material-only:        [materials]
Node + material:      [materials] -> [nodes]
Chunk + populating:   [materials, hostiles] -> [nodes] -> [chunks]
```

**This is the load-bearing pattern for nodes.** Without a chunk step, a nodes-only plan is uncommon — it would mean "add a node to an existing biome," which is plausible but probably should fold into an `[existing_chunk_modification]` directive that doesn't exist yet.

What's MISSING:

- `[WNS-GAP]` **NL3-NL7 don't list `new-node` (or `new-resource`) as a purpose bucket.** NL3's `_wes_tool` lists: `new-chunk, new-faction, new-skill, new-npc, new-quest`. NL4 lists: `new-chunk, new-hostile, new-material, new-faction, new-skill, new-quest, new-npc`. **No `new-node`.** This means: WNS NEVER directly requests a node. Nodes only appear as DAG dependencies of `new-chunk` (because the chunk needs them) or as orphan-resolution responses (because something orphan'd a node). This is, on reflection, correct — a node without a biome is a node nobody asked for. But it means:
  - The planner MUST infer node steps from chunk steps. The planner prompt's example does this correctly (`[materials] -> [nodes] -> [chunks]`).
  - The planner CAN over-zealously emit node steps when no chunk is being created. Tier 2 (locality) explicitly allows "1 of [material, node, hostile, skill]" as a standalone step, which is OK if a locality wants a unique flavor node, but the planner should be conservative.

- `[WNS-GAP]` **No firing-tier guidance for "extend an existing biome with a new node."** The current scope table says Tier 2 allows 1 node but doesn't differentiate "new node for an existing biome" vs. "new biome that needs nodes." The former is more conservative and should not trigger a chunk step. **Designer task**: tune planner prompt's scope rules to differentiate these two cases.

- `[FRAGMENT-GAP]` **Bundle's scope_hint not threaded through.** Per Agent 1 §4.6, the `scope_hint.geographic_chain` (region→province→nation names + biomes) is not in the planner's user_template. For nodes specifically, this matters because **biome locality is the node's primary flavor axis**. A planner that knows the chain is `(province:tarmouth, region:salt_moors, locality:rust_cliffs)` will write biome-rooted intents; without it, intents will be generic.

### 4.7 Rung 6 — WNS NL3/NL4 emit `<WES purpose="new-chunk">` (the trigger)

Per §4.6, nodes are *almost never* directly triggered by WNS. They are downstream of:
1. `<WES purpose="new-chunk">` — the chunk hub needs nodes (this is the dominant path).
2. `<WES purpose="new-material">` — sometimes a new material implies a new node to gather it, but the WNS-side hub doesn't know that — the planner would need to add the node step.
3. Orphan resolution at the runtime cascade — a chunk template references a `resourceId` that doesn't exist. The Request Layer creates the missing node.

What's MISSING:

- `[WNS-GAP]` **Lack of "the gathering pressure on this region is X" signal in WMS context.** When the WNS NL4 fires on the moors and sees recent WMS gathering events showing the region has been "hammered" by mining, the narrative *could* and *should* fire a `<WES purpose="new-chunk">` for a fresh deposit area OR a `<WES purpose="new-material">` for a new variant unlocked by deeper exploration. Currently the WNS NL4 prompt's `${wms_context}` is fed by L2 interpretations on locality-tagged events; gathering events ARE in the evaluator suite (`gathering_regional.py`). So this IS available; the WNS fragment just needs to be tuned to USE it. Designer task.

### 4.8 Rung 7 — WNS reads WMS L2 interpretations

WMS L2 evaluators that touch nodes:
- `gathering_regional.py` — regional gathering volume by material category.
- `gathering_chunks.py` — per-chunk gathering rates.
- `combat_kills_regional_*.py` — adjacent (hostiles near nodes can drive node-area visits).

Solid. No L2 gaps for nodes.

### 4.9 Rung 8 — WMS L1 events from player actions

The `stat_tracker.py` records via `StatStore` every gather event: `record_resource_gathered(material_id, quantity, source_node_id, chunk_id)`. These flow into L1 event rows. Solid.

---

## 5. Per-field provenance table

For every field the LLM authors. The 9-rung WMS column is walked in §5.1 for the one place I was tempted to flag `[WMS-GAP]`.

| Output field | Source layer | Source query / fragment | Existing? | Marker if not |
|---|---|---|---|---|
| `resourceId` | Tool prompt + hub `flavor_hints.name_hint` + registry-uniqueness check | name_hint flows from hub which derived from planner's `step.intent` + `step.slots.biome` + `step.slots.material_id` | Yes | — |
| `name` | Tool prompt + `flavor_hints.name_hint` | hub crafts from biome + material + node-form | Yes | — |
| `category` | Hub `hard_constraints.category` | Hub derives from `step.slots.category` (planner) | Yes | — |
| `tier` | Hub `hard_constraints.tier` | Planner's `step.slots.tier`; derived from firing_tier scope rules | Yes — but drift risk vs co-emitted material | `[FRAGMENT-GAP]` — co-emitted material tier should propagate, see §4.5 |
| `requiredTool` | Hub `hard_constraints.tool_required` | Derived from category | Yes | — |
| `baseHealth` | Tool prompt | Tier convention (T1=100..T4=800) | Yes | — |
| `drops[].materialId` | Hub `cross_ref_hints.material_id` | Required field on hub input; planner's `step.slots.material_id` | Yes — but xref extractor doesn't catch it | `[WES-SCHEMA-GAP]` — see §2.1, xref_rules._extract_node_xrefs reads wrong keys |
| `drops[].quantity` | Tool prompt | Tool's own tier-aware sizing | Yes | — |
| `drops[].chance` | Tool prompt | Tool's own primary/secondary skew | Yes | — |
| `respawnTime` | Tool prompt | Tier convention (T1/T2→fast/normal, T3/T4→slow/very_slow) | Yes — but sacred file uses `quick` which is unmapped | `[FRAGMENT-GAP]` on sacred data, see §2.1 |
| `metadata.narrative` | Tool prompt | Item_intent + prose_fragment + thematic_anchors | Partial — the parent chunk's narrative AND the WNS NL4 firing-layer narrative are stripped from the bundle slice | `[WES-SCHEMA-GAP]` — see §4.4 BundleToolSlice leak |
| `metadata.tags[]` | Tool prompt | Tool picks from allow-list | Yes | — |
| `metadata.preferred_biomes[]` (proposed) | Tool prompt | Hub's `flavor_hints.biome` + co-emitted chunk's `chunkType` | Field doesn't exist yet | `[WES-SCHEMA-GAP]` — see §2.1 proposed addition |

### 5.1 WMS-GAP walk — the one place I was tempted

The signal I almost flagged `[WMS-GAP]` for: **regional gathering pressure history at the firing address**, to drive node narrative ("the cliffs here have been worked thin in recent weeks").

The use case: when the node tool writes `metadata.narrative`, it should know whether the region is heavily-gathered, fresh, or seasonally-depleted. This shapes whether the node feels like a frontier discovery or a tired vein.

I walked the 9 rungs:

1. **Direct query**: Is there a WMS L2 row "the region's gathering pressure"? No single named L2 row. **Fail.**
2. **Adjacent events**: WMS L1 events `resource_gathered` at `address=locality:rust_cliffs` — `event_store.count_filtered(event_type='resource_gathered', address='locality:rust_cliffs', material_category='ore')` returns the raw count. **Yes — adjacent events exist.**
3. **Negative patterns**: Has the player NOT gathered ore in this region in N days? Absence is a freshness signal. Query `event_store` for last gather event at this address. Available.
4. **Aggregation**: `daily_ledger.materials_gathered_today` already tracks per-day. `gathering_regional.py` L2 evaluator outputs "region X gathered Y total quantity in last Z days" — directly tagged with material/region. **Yes — L2 evaluator builds this.**
5. **Trajectory**: `gathering_regional.py` builds severity bands (light/moderate/heavy/extreme). Same evaluator can be queried for "how does this region rank vs sibling regions." Available.
6. **Cross-layer climb**: NL4 narratives carry the *interpretation* of gathering pressure ("the cliffs here have been worked hard this season"). The bundle's `narrative_context.parent_summaries` (which IS in the WESContextBundle, just stripped by `slice_bundle_for_tool`) would carry exactly this when the firing layer is NL4. **The signal exists; the bundle slice is the leak.**
7. **Cross-entity composition**: Combine (a) gathering volume + (b) NPC dialogue mentioning the gathering ("the cliffs grow thin") + (c) faction events ("the moors raiders restrict access to the seams") = a richer "regional pressure" picture. All three available in event_store; the L2 evaluator already does similar joins.
8. **Stat / ledger lookup**: `stat_tracker.record_resource_gathered` has been recording into `StatStore`. Direct read available.
9. **Trigger history**: Has a regional gathering threshold trigger fired recently? `trigger_manager` writes to a time-indexed ledger — available.

**Verdict**: NOT a WMS gap. The signal is available through (4) + (5) L2 evaluator + (6) parent narrative. The actual gap is at the **WNS→WES bundle slice layer** (parent_summaries strip) and at the **hub→tool prompt input layer** (no `${recent_gathering_signal}` variable). Markers: `[WES-SCHEMA-GAP]` on the bundle slice (already flagged in §4.4) and `[FRAGMENT-GAP]` on the hub/tool prompt input set.

**Zero `[WMS-GAP]` markers in this trace.** WMS gives us everything needed for node narrative quality; the gaps are at the WNS→WES boundary and the wiring layer (xref, reload, registry shape). Same pattern Agent 1 found for quests.

---

## 6. Cross-references with other features (personal shopper)

### 6.1 Heavy shared infrastructure (use as-is)

- **WNS NL3-NL4 narrative weavers** — shared with chunks (the primary trigger for nodes). Nodes do not have their own WNS purpose bucket; they ride along with chunk requests via the planner DAG.
- **WES Execution Planner** — Tier-by-tier scope rules govern node generation; nodes-only plans allowed at Tier 1-2, chunk-coupled at Tier 4+.
- **WMS gathering evaluators** — `gathering_regional.py`, `gathering_chunks.py` — read-only shared substrate.
- **Tag system + tag-registry.json** — node tags drive WMS retrieval, tooltip filtering, AND visual selection (icon picker can match on tag intersection).
- **`BundleToolSlice`** — shared parent_summaries leak (§4.4) — same fix benefits all 8 tools.
- **Orphan detector** — shared. Node→material refs SHOULD be caught here, but the xref extractor reads the wrong fields (§2.1).

### 6.2 Node-specific shared with adjacent features

- **Materials (Agent 4)** — **THE PRIMARY UPSTREAM DEPENDENCY.** Every node yields 1-3 materials. The dispatcher MUST stage materials before nodes in the DAG. When materials are co-emitted in the same plan, the orphan detector MUST tolerate same-plan refs (it does). When materials are referenced but not co-emitted, orphan detection should fire — **but currently doesn't because of the xref extractor wiring gap (§2.1).**

  **Recommendation to Materials agent**: Materials should expose a per-material `narrative` summary that the nodes tool can consume via `flavor_hints.co_emitted_material_narrative`. Specifically, the material's lore (e.g. "moors-copper takes its green-blue tint from the salt that eats through the cliffs") should be threadable into the node's narrative for visual coherence.

- **Chunks (Agent 8)** — **THE PRIMARY DOWNSTREAM CONSUMER.** Chunks reference nodes by `resourceId` in `resourceDensity`. The chunk hub names which nodes appear; the nodes hub fills in their detail.

  **Recommendation to Chunks agent**: when chunks list `resourceDensity` keys for nodes that don't exist yet, the chunk hub should declare `depends_on=[nodes_step_id]` in the plan. The Request Layer also handles this reactively (orphan resolution), but pre-declared deps are cleaner and avoid the "chunk commits before its nodes do" race.

  Also: chunks should accept `cross_ref_hints.node_biome_constraint` to tell the nodes hub "this node will live in biome X, please write biome-coherent narrative." This is the §4.4 fix on the chunk-emission side.

- **Hostiles (Agent 3)** — **WEAK LINK.** A node and a hostile can occupy the same biome and share thematic anchors (the moors raiders gather copper from the seams; the seams attract the raiders). Currently this is one-way — chunks reference both, but neither references the other directly. A future enhancement could be `node.guardian_enemy_ids[]` (a node guarded by specific hostiles), but for v4 this is over-specification. Acceptable as-is.

  **Recommendation to Hostiles agent**: when hostiles have `drops[]` that reference node-yielded materials (the moors raider drops moors_copper which is also the moors_copper_seam's primary yield), the hostile's narrative should reference the node ("the raiders work the rust-cliff seams for copper to pay their tributes"). This is a soft cross-ref; declare it in hostile's narrative, not as a hard ref.

- **Skills (Agent 6)** — gather-skill prerequisites. A T4 voidstone node could plausibly require an "advanced mining" skill the player must unlock first. **Not implemented** in v4 schema (§2.1 — no `requires_skill_unlock`). Acceptable deferred. No hard cross-ref to skills tool needed in v4.

- **NPCs (Agent 2)** — weak link. NPCs can be "linked" to a node-rich biome (a moors miner NPC living in the rust cliffs) but the node itself has no NPC owner. NPCs' `home_chunk` field already provides biome-NPC coherence; nodes inherit that coherence transitively.

  No cross-ref hint needed between nodes and NPCs directly.

- **Quests (Agent 1)** — per Agent 1's seed: "Nodes don't need quest reverse-ref (gathering quests target materials, not specific nodes)." Confirmed. A gather quest says "bring me 10 moors_copper" — the player can satisfy this from any moors_copper_seam OR by killing a raider that drops moors_copper. **Nodes do NOT need to know they're a quest target.** This keeps the node schema tight.

- **Titles (Agent 7)** — no direct ref. Titles like "Moors Miner" could be threshold-granted on gathering nodes in the moors region, but that's gathering-data-driven, not node-schema-driven.

### 6.3 Where nodes diverge (flavor not shareable)

- **Spawn coupling.** Nodes are the only WES content type that's spawned WITH chunks at chunk-creation time. NPCs, hostiles, quests are spawned on-demand (NPC pathing, encounter rolls, quest acceptance). Nodes are spatial substrate. This means the node generation lifecycle is uniquely "must-be-ready-before-chunk-loads," which has no parallel in other features.
- **Silent narrative.** Nodes have `metadata.narrative` but players almost never read it (tooltip only, and most players don't tooltip nodes — they just look at the icon). The narrative quality matters less for direct player consumption and more for *WNS retrieval downstream* — the node's tags + narrative are what later WNS firings see when they pull the bundle's `wms_context`.
- **Tier-locked tool requirement.** A T4 node requires a T4 pickaxe AND silently halves effectiveness at lower tools. This is a fixed gameplay rule, not a schema axis the LLM can vary. The tool prompt should NOT invent new `requiredTool` values.

### 6.4 Recommendations to other agents (summary)

- **Materials agent**: Publish per-material `narrative` summaries the nodes tool can splice in. Coordinate with the Bundle leak fix so materials' parent narrative flows through.
- **Chunks agent**: Tighten `depends_on` for chunk steps that name fresh nodes; pre-declare instead of relying on Request Layer cleanup. Add `cross_ref_hints.node_biome_constraint` to nodes step.
- **Hostiles agent**: When your hostile drops materials shared with nodes, write hostile narrative that references the node (one-way soft cross-ref).
- **WNS / Planner+Supervisor agent**: Close the BundleToolSlice leak. Also: **decide whether `new-node` should be a WNS purpose bucket** or stay implicit-via-chunks (my recommendation: stay implicit; nodes-without-biomes are noise).
- **Wiring fixes (orchestrator-level, no single agent owns)**:
  1. `xref_rules._extract_node_xrefs` — add `drops[]` iteration so node→material orphans are caught.
  2. `xref_rules.SACRED_TOP_LEVEL_KEY[TOOL_NODES]` — change `"resourceNodes"` to `"nodes"` to match `Resource-node-1.JSON` and `ResourceNodeDatabase.load_from_file`.
  3. `data.databases.resource_node_db.ResourceNodeDatabase` — add `reload()` method walking `Definitions.JSON/Resource-node*.JSON`.
  4. `request_layer._ID_KEY_CANDIDATES["nodes"]` — add `"resourceId"` to candidates.
  5. Sacred `Resource-node-1.JSON` — replace `"quick"` with `"fast"` (9 occurrences) OR add `"quick": 30.0` to the runtime map.

Items 1-4 are wiring fixes (small, mechanical, must-do before designer playtest). Item 5 is content tuning.

---

## 7. Storage / timing design

### 7.1 The cascade-time-only architecture

User direction: nodes have no scroll-unfurl mask. They are baked into chunks at chunk-instantiation. This dictates:

- **Generation event**: WNS firing emits `<WES purpose="new-chunk">` (sometimes `<WES purpose="new-material">`) → planner adds nodes step to plan → hub → tool → static node JSON → ContentRegistry stages → on commit, generated file written + database reload.
- **Critical**: the entire cascade (materials → nodes → chunk_template) must complete and reload BEFORE the player walks into the new chunk. If it doesn't, the chunk silently spawns with what's available (orphan-skip behavior, see §1.3.d).
- **Backstop**: when a player approaches a chunk whose template references orphan node IDs, the Request Layer kicks in (`_spawn_from_template` doesn't fire it directly — that's a chunk-load-time check, not a generation-time event). **This means orphan resolution for nodes happens at TEMPLATE CREATION time, not at CHUNK LOAD time.** The Request Layer fires when an executor_tool emits a chunk-template that references unknown nodes — it fires DURING the cascade, not during gameplay. Once the template is committed, the chunks are frozen — orphan nodes will skip forever for that chunk.

### 7.2 Pool sizing — NOT a node concept

Quests need a pool because the player encounters them on-demand. Nodes are baked. There's no "node pool" per giver. The runtime equivalent of a "node pool" is just: the `ResourceNodeDatabase` singleton itself, with every registered node available to chunk spawn.

What MATTERS for node sizing is the **diversity of registered nodes per biome**. If only 3 nodes are registered for the moors and 100 chunks spawn there, all 100 chunks look the same. So:

- **Designer goal**: aim for 4-8 distinct nodes per biome at launch. Each chunk template selects 2-5 of them via `resourceDensity`, with variance in density weights.
- **Generation cadence**: when WNS fires `<WES purpose="new-chunk">` on a fresh biome, the planner DAG should request 2-4 materials, 4-6 nodes, 1-2 hostiles. The 4-6 nodes give the biome internal variety from the start.
- **Refresh cadence**: when WNS fires NEW chunk templates for the SAME biome (because the narrative evolved — say the moors got a new sub-region), the planner should reuse existing biome materials/nodes where possible. Only add new ones when the narrative explicitly calls for them. This is the diversity-vs-saturation balance — Agent 8 (Chunks) owns this.

### 7.3 What happens when the cascade lags

Scenario: player walks into a chunk whose template references `moors_copper_seam` but the Request Layer's parallel run on `wes_tool_nodes` for that node hasn't completed. The chunk's `_spawn_from_template` runs synchronously, calls `db.get_node("moors_copper_seam")`, gets None, skips.

Current behavior: the chunk renders with whatever nodes ARE in the database. If zero match, the chunk is empty. Player sees emptiness, no narrative hint.

**Recommended degradation**: when a chunk template's referenced nodes are missing, the chunk's `metadata.narrative` should be elevated to a brief tooltip-on-empty ("the cliffs here are bare of the rumored copper today — perhaps next week"). This requires:
- Tracking which expected resourceIds didn't resolve at spawn.
- Rendering a tooltip on the empty chunk explaining it.
- Optional: scheduling a retry on the next chunk reload.

This is a **runtime feature, not a node-schema feature.** Out of scope for the nodes tool prompt. But the Chunks agent should hear it.

### 7.4 What the runtime touches

When a node is committed and reloaded:

1. `ResourceNodeDatabase.nodes[resourceId] = ResourceNodeDefinition(...)`.
2. `_trees | _ores | _stones` cached lists updated by category.
3. `_tier_map[resourceId] = tier`.
4. `ICON_NAME_MAP` — **MANUALLY KEPT** sacred mapping for legacy PNG names. WES-generated nodes will fall through to `get_icon_name()` returning the resourceId as-is, looking for `resources/<resourceId>.png`. If no such PNG exists, the icon renders as a placeholder. **This is acceptable for v4 (designer reviews icon needs post-generation), but is a `[FRAGMENT-GAP]` for visual quality.**

### 7.5 Icon resolution — the visual layer

The tool prompt does NOT govern visuals; the visual comes from `resources/<resource_id>.png`. WES-generated nodes default to needing a new PNG. Currently the asset pipeline has NO automatic PNG generation; a designer either:
- Adds a PNG matching the resourceId.
- Adds an `ICON_NAME_MAP` entry pointing to an existing PNG (e.g. all "copper-form" nodes share one icon).

**Recommendation**: the nodes tool prompt could optionally emit a `metadata.icon_hint` field — a free-text descriptor — that a future asset-gen pipeline could consume. Adding this now (even unused) leaves the schema room. **Marker**: `[WES-SCHEMA-GAP]` — proposed `metadata.icon_hint` field.

---

## 8. Diversity & creativity design

The diversity dials for nodes, ranked by impact:

### 8.1 Biome-locking

The single biggest diversity dial. A `moors_copper_seam` should appear in moors chunks only; an `arctic_iron_outcrop` should appear in arctic chunks only. Currently enforced only by the chunk template's `resourceDensity` choices — the node itself doesn't carry biome metadata.

Implementation:
- Add `metadata.preferred_biomes[]` (see §2.1) — soft constraint the chunk hub respects.
- Hub's `recent_registry_entries` filter — query for nodes already in this biome to avoid duplication WITHIN the biome (a moors with three copper-form nodes is overstaffed; the hub should diversify form).

### 8.2 Form variety within a category

Tree, ore, stone, fishing. Within "tree" — what forms? Standing trees (the default), fallen logs, stumps with bark, sapling clusters, ancient grove markers. The sacred file uses only "tree" semantically; a node named `fallen_oak_log` is still category=tree. Diversity comes from:
- Naming conventions (the tool prompt's `<biome>_<material>_<form>` pattern).
- Sprite variation (icon layer — see §7.5).
- Yield variation (a fallen log might yield "many" oak_log immediately but never respawn; a standing tree yields "several" but respawns).

The tool prompt should explicitly encourage form variety per category. Currently it doesn't — designer task.

### 8.3 Tier-coherence vs tier-spread

A region should have nodes spread across 2-3 tiers, not a single tier. The salt moors might have T1 fishing spots (carp pools at the shore), T2 ore (rust copper seams), T3 stone (voidstone shards in the deep cliffs). This creates a gradient within the biome — the player progresses through it.

Currently enforced by chunk template `tier_range` (a `(min, max)` tuple per chunk-danger-level). The hub's `hard_constraints.tier` is single-valued per node spec, but the planner can emit multiple node specs at different tiers under one chunk step.

Designer task: planner prompt example should show a multi-tier node batch ("primary T2 node + secondary T1 + rare T3").

### 8.4 Yield-table variety

The slot machine: every node yields its primary material at "many" + "guaranteed." Slop.

The LLM, per the tool prompt: 1-3 drops, with primary skewing high but not always guaranteed, with optional secondary/tertiary drops that flavor the biome (a moors copper seam drops `moors_copper` primary + `salt_crystal` secondary + `rust_dust` tertiary). This is *the* feature where LLMs visibly beat the baseline.

Currently the tool prompt says 1-3 drops; nothing forces variety in the secondary slot. Designer task: tune the prompt to encourage at least one secondary drop on T2+ nodes.

### 8.5 Respawn-time variety

T1/T2 default to fast/normal (30s/60s). T3/T4 default to slow/very_slow (120s/300s). Beyond that:
- "Narrative one-shot" nodes — null respawn, used for rare-find moments (a single voidstone shard in a chunk that depletes permanently).
- "Seasonal" nodes — currently no schema support. A future field could be `respawnTrigger: time | season | event` for narrative-driven respawn. Not v4 scope.

### 8.6 Tag-driven WMS feedback loop

Node tags drive WMS retrieval. A node tagged `[ore, metal, copper, salt, starter]` produces L1 gather events that L2 evaluators aggregate by tag. When the WNS NL4 fires next on the moors, its `${wms_context}` will include "the region has heavy gathering of [salt, copper] tagged events." This SHAPES the next node generation — the cycle feeds itself.

This is the deepest diversity loop: nodes you place now influence what gets placed later, because the WMS sees the player's interaction with them and the WNS interprets that into narrative pressure.

### 8.7 Player progression sensitivity

Unlike quests, nodes don't materialise per-player at encounter time. They are world-state. So player-fit is a generation-time concern, not an encounter-time one. The Planner sees `registry_counts` near the firing address but no player-fit signal. **This is acceptable** — the world should have nodes the player can't yet harvest (T4 nodes visible but immovable; this creates "I'll come back at level 30" moments).

What we SHOULD avoid: a starter region with only T4 nodes (player can't progress). The planner's scope-by-firing-tier rules handle this implicitly (Tier 1-2 firings produce T1-T2 content; Tier 4 firings produce T2-T4 content).

### 8.8 Repetition guards

The hub's `recent_registry_entries` is the primary defense against repetition. To make it work:
- The orchestrator must filter recent_registry_entries to nodes in the SAME biome (per §4.5).
- The hub prompt should be augmented: "if recent_registry_entries lists 3+ nodes in this biome, prefer a thematically distinct form (if 3 ores, propose a stone; if 3 trees, propose a fishing spot)."
- The hub should track WITHIN-PLAN diversity — if a single plan emits 6 node specs, they should span at least 2-3 categories, not all be ores.

Designer task: tune the hub prompt's diversity guidance.

---

## 9. Speculative future endpoints

### 9.1 `wes_node_evolution` — biome-aging nodes

Per memory `chunk_evolution_future_idea.md`: chunk templates form a tree; existing instances roll a small chance to evolve down the branch. Nodes could mirror this — a tier-3 copper seam in a heavily-gathered region could evolve to a tier-2 "depleted seam" template, OR a tier-1 fresh node could evolve to a tier-2 "matured" node.

Sketch:
- **Trigger**: at WNS NL4+ firing, check WMS gathering pressure on the region. If pressure exceeds threshold for N days, fire `<WES purpose="evolve-node">` on candidate nodes.
- **Inputs**: original node template + gathering history + region narrative state.
- **Outputs**: a patch template OR a sibling node with downgraded yields and a "depleted" narrative.

Endpoint count: +1 LLM task. Probably premature pre-release — schema room left.

### 9.2 `wes_node_seasonal_variant` — season-locked variants

Some nodes only appear in certain WNS-narrative-driven seasons (a winter-only "frost-laced oak"). Requires seasonal infrastructure in WMS (currently absent — no season concept). Out of scope for v4.

### 9.3 `wes_node_guardian` — hostile-guarded nodes

A T4 voidstone node guarded by a specific T3 hostile that spawns near it. Currently expressed via chunk-level co-occurrence (chunk template lists both). A node-specific guardian field could tighten the spatial coupling.

- **Trigger**: planner emits a node step for a rare/legendary tier and a hostile co-emit. Add `metadata.guardian_enemy_ids[]` on the node.
- **Runtime**: chunk spawn pipeline places the guardian hostile within N tiles of the node.

Endpoint count: 0 new — schema extension only. Worth considering for v4.5+.

### 9.4 `wes_node_modifier` — post-creation tuning

Similar to `wes_quest_modifier`. When a region's narrative shifts substantially after a node was created (the moors-copper trade collapsed because of a famine), existing nodes should update their narrative ("the seams here are bitter now; the salt has gone bad") AND their yields (chance drops to "rare" from "high").

- **Trigger**: WNS thread closure on a region that has nodes attached.
- **Inputs**: original node template + closing-thread narrative + recent WMS interpretations.
- **Outputs**: a patch over the node template.
- **Latency budget**: not player-facing; cascade-time work.

Endpoint count: +1 LLM task. Worth considering post-launch.

### 9.5 Big-picture: the 2-endpoint node pipeline could grow to 4-5

Current: `wes_tool_nodes` + `wes_hub_nodes` (2).
With speculatives: + `wes_node_evolution` + `wes_node_modifier` + `wes_node_guardian` (data extension only).
Pragmatic count: **3 endpoints** when the system reaches maturity. The two shipped now are the load-bearing minimum, and given nodes' silent-feature nature (no player-spoken narrative), more endpoints than that is gold-plating.

---

## End

Three load-bearing fixes this trace surfaces, in priority order:

1. **Wire the node→registry pipeline correctly.** Five small fixes (xref extractor, SACRED_TOP_LEVEL_KEY, reload method, request_layer key candidates, sacred file `quick` value) together unblock the entire node generation pipeline at the registry/reload boundary. Without these, every WES-committed node is silently dropped on the floor — the most expensive form of failure because it looks like a working system.

2. **Close the `BundleToolSlice` parent_summaries leak** — same issue Agent 1 flagged, same fix benefits all 8 tools. For nodes specifically, the leak strips the chunk's biome narrative + the parent NL4 region narrative, which together are what would give the node `metadata.narrative` field its biome-rooted texture.

3. **Co-emit material payload to nodes hub** — the hub needs to see what material it's writing a node for, including the material's narrative, tier, and lore. The dispatcher should attach staged material rows from the same plan to the nodes hub input. Same pattern as Agent 1 recommended for quests (NPC giver narrative → quest tool).

Everything else in this trace — diversity dials, biome-locking, evolution endpoints, schema enhancements — is downstream of those three.

**Cross-feature note for the central agent**: Wave 2 has Materials and Chunks as the agents most-coupled to Nodes. Nodes are literally the bridge between Materials (the LEAF) and Chunks (the SUBSTRATE). The five wiring fixes in §2.1 are all sitting in code that any of the three agents (Materials, Nodes, Chunks) could see. Coordinate the fix landing in one orchestrator-level pass so the registry-reload-orphan triangle is sealed before designer playtest.
