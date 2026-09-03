# Tag Usage Map — the systematic "when we add/change a tag, update these" list

**Purpose:** tags are load-bearing across many systems. This is the single checklist so that
when a tag is **added, renamed, or invented**, we can walk one list and update everything.
Created 2026-08-11 during the tag-driven minigame redesign. Keep this current.

---

## 0. The two tag namespaces (do not conflate)

| Field | Lives on | Vocabulary | Validated? | Drives |
|---|---|---|---|---|
| `metadata.tags` | materials **and** outputs | descriptive: element / family / quality / behavior | **NO — free-form** | UI/search, **CNN color encoding**, LLM prompt, **(new) crafting minigames** |
| `effectTags` | outputs, skills, weapons | functional combat vocabulary (registered) | YES — `Definitions.JSON/tag-definitions.JSON` | effect executor / combat, class affinity, renderer |

Materials carry **only `metadata.tags`**. The minigame system reads `metadata.tags`
(material tags = per-ingredient behavior; output tags = per-recipe target/character).

**Godot note:** on `MaterialDefinition`, tags are a raw `JsonNode` array (`Models.cs:30`,
order preserved). On `EquipmentItem` they are a typed `List<string>` (`EquipmentItem.cs:39`).

**Migration constraint:** content JSON (including material tag lists) is OFF LIMITS. The
minigame effect bank is a **new config** that maps *existing* tags → effects. We never edit
a material's tag list.

---

## 1. Material tag vocabulary (~66 distinct, from `items-materials-1.JSON` + `items-refining-1.JSON`)

- **Element:** `fire` `water` `earth` `air` `lightning` `ice` `light` `dark` `void` `chaos`  *(refined alloys add `frost`)*
- **Material-family:** `metal` `wood` `stone` `elemental` `monster` `leather` `scales` `carapace` `fang` `gel` `blood` `essence` `metallic` `crafting` `fishing` `material` `alloy` `plank`
- **Specific-material (refining):** `copper` `iron` `tin` `steel` `mithril` `bronze` `adamantine` `orichalcum` `oak` `ash` `ironwood` `ebony` `worldtree` `exotic`
- **Quality/tier-descriptor:** `basic` `refined` `starter` `standard` `common` `uncommon` `rare` `fine` `quality` `advanced` `legendary` `mythical` `ancient` `precious`
- **Property/behavior:** `durable` `strong` `sharp` `flexible` `versatile` `layered` `living` `radiant` `spectral` `magical` `temporal` `memory` `quantum` `impossible`

> Most materials have **exactly 3 tags**, ordered but not to a rigid slot schema. Position 0 is
> usually a family/quality anchor, so precedence weighting must run over **effect-bearing tags only** (see §3).

---

## 2. Tag consumers (update ALL that apply when a tag changes)

| # | Consumer | File(s) | Namespace |
|---|---|---|---|
| 1 | **CNN crafting classifier** (element→hue, quality→saturation) | `systems/crafting_classifier.py:88,189,210` | `metadata.tags` |
| 2 | LLM item generator prompt | `systems/llm_item_generator.py:478,899` | `metadata.tags` |
| 3 | **Crafting minigames (NEW)** — effect bank | `Game-1-Godot/scripts/minigames/*` + `minigame_tag_effects.json` | `metadata.tags` |
| 4 | Effect executor / combat | `Combat/combat_manager.py`; Godot `EffectExecutor.cs`, `TagAttackOrchestrator.cs`, `WeaponTagModifiers.cs` | `effectTags` |
| 5 | Tag registry / parser / debug | `core/tag_system.py`, `core/tag_parser.py`, `core/tag_debug.py` | `effectTags` |
| 6 | Class affinity bonuses | `systems/class_system.py`, `data/databases/class_db.py` | `effectTags` |
| 7 | Skill system | `data/databases/skill_db.py` | skill `tags` |
| 8 | Renderer visual selection | `rendering/renderer.py` | tags |
| 9 | Registry / validation (functional only) | `Definitions.JSON/tag-definitions.JSON` | `effectTags` |
| — | WMS/WNS narrative taxonomy (separate — not item tags) | `world_system/world_memory/tag_library.py`, … | narrative |

---

## 3. "I am adding / renaming / inventing a tag" — the checklist

1. **Is it a material descriptive tag** (`metadata.tags`) or a **functional combat tag** (`effectTags`)? Different namespaces, different steps.
2. If **functional** → register it in `Definitions.JSON/tag-definitions.JSON` (consumers #4–#9).
3. If **material descriptive**:
   - a. **CNN (#1):** if it's an element or quality tag, add a hue/saturation mapping (`crafting_classifier.py`), else the classifier ignores it (safe).
   - b. **Minigame effect bank (#3):** add a `tags."<name>"` entry to `minigame_tag_effects.json` with per-discipline effects (see §4). **This is required for every material tag** — an unbanked tag falls back to a neutral default (logged).
   - c. LLM prompt (#2) picks it up automatically (reads the list).
4. Run the **coverage check**: every distinct tag in `items-materials*.JSON` + installed `Update-*/` material files must have a bank entry. (Tool TBD — a script that diffs material tags vs bank keys.)
5. Update **§1** of this doc with the new tag.

> Update folders: `update_loader.py` merges `Update-*/` materials at runtime (gated by
> `updates_manifest.json`). Today no real new material tags ship there, but any that do are live —
> so the coverage check must scan installed update folders too.

---

## 4. Minigame effect bank — schema (DRAFT, per-discipline effects fill in as designs lock)

New system config: `Game-1-Godot/.../minigame_tag_effects.json`. One entry per material tag.
Each tag has an **archetype** (its "feel") + per-discipline effect params. Unlisted disciplines
use the archetype default.

```jsonc
{
  "tags": {
    "fire":  { "archetype": "pressure",
      "alchemy":     { "stabilityBase": +12, "stabilityMult": 1.15, "cookWindow": -0.25 },
      "refining":    { "lane": "space", "motif": [1,0,1], "densityMod": +0.20 },
      "engineering": { "timeMod": -0.25, "moveMod": 0.0 },
      "smithing":    { "heroAbility": "flame_nova" },
      "enchanting":  { "nodeChallenge": "moving_flame", "hazardMod": +0.20 } },
    "ice":   { "archetype": "deliberate",
      "engineering": { "timeMod": 0.0, "moveMod": -0.20 },
      "alchemy":     { "stabilityBase": -10, "stabilityMult": 0.90, "cookWindow": +0.15 },
      "enchanting":  { "nodeChallenge": "slippery" } },
    "metal": { "archetype": "structure",
      "alchemy":     { "stabilityBase": -6, "stabilityMult": 1.05 },
      "smithing":    { "heroStat": { "armor": +1 } } }
    // …one entry per tag in §1…
  },
  "archetypes": {
    "pressure":   "raises tempo / cuts time — fire, lightning, chaos",
    "deliberate": "cuts moves / slows — ice, stone, earth",
    "structure":  "stabilizing / defensive — metal, durable, layered",
    "volatile":   "amplifies swings — void, chaos, blood, essence"
  }
}
```

**Design language (the intent behind the numbers):** a tag maps to a *feeling*. `fire`/`lightning`
= pressure (less time, more tempo). `ice`/`stone` = deliberation (fewer moves, more thinking).
`metal`/`durable` = structure (stabilizing). `void`/`chaos` = volatility (bigger swings, higher
ceiling + risk). Quality tags (`basic`…`mythical`) scale **difficulty/target sharpness**, not character.

**Precedence (from the alchemy design):** within one material, weight its **effect-bearing** tags
(skip pure family/quality anchors) by order: 1st = 4, 2nd = 3, 3rd = 2, 4th+ = 1. Resolves
intra-material conflicts (e.g. `ice` stabilizes vs `metal` structures → earlier tag wins).

---

## 5. Open items
- [x] Populate the bank for all ~66 tags — **DRAFT in [MINIGAME_TAG_EFFECTS.md](MINIGAME_TAG_EFFECTS.md)** (archetype + per-discipline effects + Alchemy interaction matrix). Awaiting red-pen.
- [ ] Coverage-check script (material tags vs bank keys, incl. update folders).
- [ ] Decide whether to formalize/validate the material-tag vocabulary (currently free-form).
