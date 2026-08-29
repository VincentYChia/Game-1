# MCP Concern-Registry Architecture for Game-1: Grounded Blast-Radius for Cross-Cutting Change

**Status:** BUILT — Phases 1–5 all implemented and verified (2026-08-29). Code: [`Game-1-modular/tools/concern_mcp/`](../Game-1-modular/tools/concern_mcp/) (stdlib-only, 9 MCP tools, 19 tests). Real-repo index ≈ 535 concepts / ~2,990 binding sites / 123 files, ~2s build; `blast fire` returns 72 grounded sites across 7 coupling groups (authority / code_dispatch / db_junction / ml_label / csharp_mirror / vfx / json_value). `DbRowProbe` opens the real `crux-foundry/runs/*/wms/*.db` files read-only. Grounded coordinates in `tools/concern_mcp/coordinates.py`. This document is the design of record; §6 phase plan is now history.
**Target repo:** Game-1 (`Game-1-modular/` Python ~168k LOC, `Game-1-Godot/` C# ~45k LOC, ~4.8k JSON, heavy markdown)
**Integration point:** Claude Code via an NDJSON-over-stdio MCP sidecar
**Backbone:** `C-WMSPattern` (reuse the repo's own WMS tag-indexed SQLite substrate), hardened with runner-up ideas and three adversarial-verify fixes.
**Provenance:** Designed via a 16-agent workflow (6 code tracers grounding the real tag web → 3 independent architectures → judge panel [C-WMSPattern 150 / B-ConcernGraph 146 / A-Composition 126] → 3 adversarial change-scenario stress-tests → synthesis). All load-bearing citations verified against source.

---

## 0. Why this exists (problem + why not an off-the-shelf tool)

**The failure being solved.** When the developer asks the AI assistant for a *fundamental* change to a cross-cutting concern — the archetype being the **tag system** — the change fails because the finer details of the scattered web of connections escape the assistant's context window. Tags are everywhere: core game code, the WMS/WNS SQLite tag taxonomy + junction tables, JSON content values, CNN/LightGBM label vocabularies, the C# Godot port, and VFX/minigame branches.

**Why a generic code-graph MCP (Serena, code-graph-rag, Cognee, etc.) is not enough.** Those follow `import`/`call`/`reference` *symbol* edges. But the load-bearing tag couplings in this repo are **string-value couplings that never reference each other symbolically**, and they **fail silently** (no compile error). See §1. A call-graph tool is *structurally incapable* of surfacing them. The right tool composes an off-the-shelf LSP MCP for the symbol half and adds a purpose-built **concern overlay** for the string web (§8).

**Landscape considered (2026-08 research).** Families surveyed: repo-map/PageRank (Aider), AST chunking (cAST/ASTChunk), precise code intelligence (SCIP + `scip-python`/`scip-dotnet`, Sourcegraph/Glean), code knowledge graphs / MCP servers (Serena, code-graph-rag, stakgraph, codebase-memory-mcp, infigraph, blarify, CodeGraphContext), agent-memory frameworks (Mem0, Letta, Zep/Graphiti, Cognee, GraphRAG/LightRAG). Conclusion: the **symbol-oriented** tools are reusable for the call spine but *none* model json-value / db-junction / ml-label coupling; that is the differentiated custom piece here.

---

## 1. Core insight & design principle

### The problem is *concern*-shaped, not *symbol*-shaped

The concept **`fire`** — or the concern **"tag parsing"** — is realized as a scattered web of string-value couplings that never reference each other symbolically:

- **`json-value`** — the literal `"fire"` sits in a `combatTags` array in `Skills/skills-skills-1.JSON`, matched at runtime by `==` in `core/effect_executor.py:228`. No symbol connects them.
- **`db-junction`** — `fire` lives as a SQLite row `(tag_category='element', tag_value='fire')` in `world_system/world_memory/layer_store.py` junction tables. The tables never reference the JSON or the Python.
- **`ml-label`** — `fire` is a frozen positional slot `ELEMENT_HUES['fire']=0` in `systems/crafting_classifier.py`, mirrored across four encoder copies and baked into `*.keras`/`*_model.txt` weights.
- **`csharp-mirror`** — the same literals re-appear in `Game-1-Godot/src/Game1.Core/Combat/EffectExecutor.cs` and, unmirrored, in ~388 tag-keyed `Dictionary` entries across five `scripts/minigames/*.cs` files.
- **`string-literal-dispatch`** — `if special_tag == 'lifesteal'` chains that silently no-op on an unknown string.

None of these are edges in any symbol graph, and they **fail silently**: a renamed value produces an "Unknown tag" warning at best (`core/tag_parser.py:60`), a dead count column, or a fallback hue — never a compile error. Details escape the context window precisely because they are invisible to the tools the assistant reaches for.

### Design principle 1 — Index the *concern*, layered on top of a symbol layer

The unit of memory is a **CONCEPT** (a cross-cutting string identity: a tag value, a category name, a parse-key, a db-junction column, an ML feature slot), and its members are **BINDING SITES** (every real place that concept is bound, of any coupling type). This mirrors the repo's own WMS pattern where an *event* has *tags*. We do **not** rebuild the symbol layer — we compose an off-the-shelf LSP MCP for that (§8) and add the non-symbolic layer the LSP cannot see. The two are unioned at query time so the assistant sees *both* the call spine and the string web in one ranked result.

### Design principle 2 — Grounded pointers, not summaries

Every binding site resolves to something the assistant can **literally open on demand**: a `file:line`, a `db.table.column`, or a `model_file:feature_slot`. The tool returns *locations plus a one-line role and a `silent_failure` note*, never a prose recap of the code. This keeps the payload small enough to survive the context window while guaranteeing the assistant pulls ground truth for exactly the sites it will edit. The registry is a **map to the truth**, not a compressed copy of it.

### Design principle 3 — Reuse the substrate the team already debugs in

The team thinks in `category:value` tags and SQLite junctions (the WMS pattern). The registry's storage, its `HAVING COUNT(DISTINCT tag_category || ':' || tag_value)` intersection query (verbatim from `layer_store.py:271`), and its `calculate_relevance` overlap ranking (from `tag_relevance.py:53-57`, exact=1.0 / same-category=0.3) are near-copies of tested repo code. Zero embeddings, zero vector DB — tags are exact strings, so blast-radius is an indexed equality join, both deterministic and cheap.

---

## 2. The index / data model

### Two-layer model: structural spine + concern overlay

```
┌─────────────────────────────────────────────────────────────┐
│  SYMBOL LAYER (composed, off-the-shelf LSP MCP)              │
│  find_symbol / find_referencing_symbols / call hierarchy    │
│  Python (pyright/jedi) + C# (OmniSharp/Roslyn)              │
│  → the CALL SPINE: TagRegistry→TagParser→EffectExecutor,    │
│    parse() call-sites, EffectConfig field references         │
└─────────────────────────────────────────────────────────────┘
                          ▲ unioned at query time
┌─────────────────────────────────────────────────────────────┐
│  CONCERN OVERLAY (the custom piece — SQLite: concern.db)    │
│  concepts + binding_sites + concept_edges                   │
│  → the STRING WEB the LSP cannot see:                        │
│    json-value, db-junction, ml-label, csharp-mirror,        │
│    string-literal-dispatch, output-contract-field            │
└─────────────────────────────────────────────────────────────┘
```

The overlay stores **only what the symbol layer misses**. It never re-derives call edges — those are fetched live from the LSP MCP per query and merged. This keeps the persisted index small and avoids owning symbol-freshness.

### Table: `concepts` (mirrors a WMS "event")

```sql
CREATE TABLE concepts (
  id            TEXT PRIMARY KEY,   -- "tagvalue:fire", "category:damage_type", "parsekey:combatTags"
  concept_kind  TEXT NOT NULL,      -- MIRRORS tag_category (see enum below)
  concept_value TEXT NOT NULL,      -- MIRRORS tag_value: the literal string
  taxonomy      TEXT NOT NULL,      -- which parallel universe: combat_effect | wms | wns
                                    --   | crafting_recipe | enchant_effect | ml_material | none
  authority_ref TEXT,              -- file:line of the source-of-truth declaration
  aliases_json  TEXT DEFAULT '[]', -- resolved alias chain (blink->teleport) for query-time expansion
  is_dynamic    INTEGER DEFAULT 0, -- WMS-style: accepts any value vs frozenset
  governance    TEXT,              -- 'content-frozen' for CLAUDE.md sacred-boundary JSON, else null
  summary       TEXT               -- one-line "what this is / what breaks if renamed"
);
CREATE INDEX idx_concept_pair ON concepts(concept_kind, concept_value);  -- the WMS signature index
```

`concept_kind` enum (drawn from the concern map's own vocabulary so the map *is* the schema):
`tag_value | tag_category | alias | param_key | db_column | junction_shape | ml_feature_slot | slot_type | discipline | element_synonym | state_name | output_contract_field`

`output_contract_field` is added per adversarial-verify Scenario 3 (§7) so `EffectConfig.geometry_tag`/`damage_tags`/`special_tags` become first-class concepts — the actual blast radius of a *structural parser refactor*.

### Table: `binding_sites` (mirrors "tags on an event") — the atom of grounding

```sql
CREATE TABLE binding_sites (
  concept_id      TEXT NOT NULL,
  site_kind       TEXT NOT NULL,   -- definition | parser | consumer | json_value | db_schema
                                   --  | ml_label | csharp_mirror | vfx | test | doc | output_contract_field
  language        TEXT NOT NULL,   -- python | csharp | json | sql_ddl | ml_binary
  file            TEXT NOT NULL,
  line            INTEGER NOT NULL,  -- REAL, openable file:line (or db-column / feature-slot locator)
  locator_extra   TEXT,            -- {db,table,column} or {model_file,slot_index} as JSON when not a line
  coupling_type   TEXT NOT NULL,   -- symbolic | json_value | db_junction | ml_label
                                   --  | string_literal | csharp_mirror | allowlist_generation
  role            TEXT NOT NULL,   -- one-sentence "what this site does with the concept"
  silent_failure  TEXT,            -- LOAD-BEARING: what happens on rename WITHOUT error
                                   --   ("falls to hue 0", "unknown-tag warning effect dropped",
                                   --    "count column reads 0", "NEW CATEGORY dropped w/ NO warning")
  mirror_group    TEXT,            -- non-null links sites that must stay byte-identical
  pinned_by_test  TEXT,            -- golden/test file that guards this mirror, or null (=UNGUARDED)
  editable        INTEGER DEFAULT 1, -- 0 for content-frozen JSON (steer to alias, not rewrite)
  content_hash    TEXT,            -- for incremental staleness
  FOREIGN KEY (concept_id) REFERENCES concepts(id)
);
CREATE INDEX idx_bs_concept ON binding_sites(concept_id);
CREATE INDEX idx_bs_mirror  ON binding_sites(mirror_group);
```

### Table: `concept_edges` — concept-to-concept coupling (answers "what *else* moves")

```sql
CREATE TABLE concept_edges (
  src_concept_id TEXT NOT NULL,
  dst_concept_id TEXT NOT NULL,
  edge_kind      TEXT NOT NULL,   -- alias_of | drifts_from | same_universe | member_of_category
                                  --  | feeds_ml | address_of | mirrors | shadows
                                  --  | category_requires | ordering_invariant | pinned_by_golden
  note           TEXT
);
```

Key edge kinds hardened from the runner-ups and adversarial verify:
- **`drifts_from`** — seeded from the grounded concern map (`single`↔`single_target`, `fire`↔`ice`↔`frost`, `poison`↔`poison_status`↔`vulnerable`). Lets `blast_radius('fire')` pull its divergent twin.
- **`shadows`** — two *deliberately decoupled* vocabularies that share a string by coincidence (combat `damage_type:element` vs WMS L1 `element`). Flagged so the assistant is *told* they are separate, preventing the conflate-the-three-taxonomies error.
- **`category_requires`** (Scenario 1 fix) — links a `tag_category` concept to the fixed structural sites a *new category* needs (parser bucket branch, `EffectConfig` field ×2 languages, executor method+wiring ×2, C# switch case, VFX palettes, golden fixture).
- **`ordering_invariant`** (Scenario 3 fix) — links `base_damage`-extraction to synergy-application in both languages (`tag_parser.py:99-104` / `TagParser.cs:129-132`), carrying the "synergy must not retro-update base_damage" caveat.
- **`pinned_by_golden`** (Scenario 3 fix) — links the parser output contract to `conformance/dump_databases.py:config_row` and the C# golden tests, making enforcement visible rather than incidental.

---

## 3. Components & build/extraction pipeline

`PolyglotIndexer` orchestrates the extractors below, each emitting **uniform NDJSON rows** into `concern.db`. Every extractor is **per-file idempotent** (delete a file's rows, re-insert) so a changed file reindexes in isolation. Build order matters: authorities first (so downstream sites resolve alias chains at insert time).

### 3.1 `VocabularyExtractor` — authorities first

Parses source-of-truth declarations into `tag_value` / `tag_category` concepts + alias/conflict/synergy edges. One **recipe per authority**:

| Authority file | What it seeds |
|---|---|
| `Definitions.JSON/tag-definitions.JSON` (`categories` block; `tag_definitions`) | Combat taxonomy: `tag_category` nodes + member `tag_value` nodes; `aliases`/`alias_of`/`conflicts_with`/`synergies` edges. Sets `authority_ref`. |
| `world_system/world_memory/tag_library.py` (`ALL_CATEGORIES`; `validate_tag`; `render_assignable_tag_allowlist`) | WMS 65-category taxonomy; `is_dynamic` frozenset flags; allow-list/enforcement coupling. |
| `world_system/wns/narrative_tag_library.py` + `world_system/config/narrative-tag-definitions.JSON` | WNS taxonomy; records the WNS→WMS `validate_tag(layer=7)` fallback as a `same_universe` edge. |
| `items.JSON/items-materials-1.JSON` (`metadata.categories`) + LightGBM `_build_vocabularies` | ML material vocab ordinals (frozen sorted order). |

**Correctness note:** prefer *parsing* `tag_library.py`'s dataclasses via `ast`/`libcst` over *importing* and calling `render_assignable_tag_allowlist` (the import-and-call trick breaks on import side-effects). Keep a *sandboxed import as an optional CI verification pass* (assert AST-derived set == runtime output) — never on the interactive freshness path.

### 3.2 `PyExtractor` — Python AST (targets `Game-1-modular/`)

`ast` walk capturing string-literal couplings a call graph misses:
- `== 'lifesteal'` comparisons in if/elif chains → `string_literal` dispatch sites (`core/effect_executor.py:228-253`, incl. the dead `summon` TODO at 253).
- category-string literals `'geometry'/'damage_type'/'status_debuff'/'unknown'` → `tag_category` sites (`core/tag_parser.py:46-61`). A *new* category not matching any elif is dropped with **no** warning (bypasses the `== 'unknown'` branch at line 60) — `silent_failure` records this.
- dict/HashSet key literals → modifier-table sites: `entities/components/weapon_tag_calculator.py`, the 5 processor classes in `core/crafting_tag_processor.py`, `animation/combat_particles.py:22-31` (`DAMAGE_SPARK_COLORS`), `rendering/visual_colors.py`.
- `.get('combatTags')` / `.get(...)` param-key reads → `param_key` sites with `silent_failure='misnamed key → empty list → skill drops to non-combat path'` (`data/databases/skill_db.py:187`, `equipment_db.py:364`, `data/models/skills.py:62-75`).
- **`output_contract_field`** (Scenario 3 fix): a visitor for `ast.Attribute` access on a value typed `EffectConfig` — records every `config.geometry_tag`/`config.damage_tags`/`config.special_tags` read across `core/effect_executor.py` (~25 sites), `core/tag_debug.py:92-115`, `tests/test_knockback.py`.

### 3.3 `CsExtractor` — Roslyn (targets `Game-1-Godot/src` + `Game-1-Godot/scripts`)

Roslyn syntax walk emitting the same NDJSON shape:
- **Certified Core mirrors** (`mirror_group` paired to Python, `pinned_by_test` set): `src/Game1.Core/Combat/EffectExecutor.cs:216-234` (↔ `effect_executor.py:228-250`), `WeaponTagModifiers.cs` (↔ `weapon_tag_calculator.py`), `Tags/TagParser.cs:63-82` switch (↔ `tag_parser.py:46-61`), `Crafting/TagProcessors.cs` (↔ `crafting_tag_processor.py`), C# `EffectConfig.cs` fields (↔ Python `EffectConfig`).
- **Net-new, UNMIRRORED Godot surface** (`mirror_group=null`, `pinned_by_test=null`, `silent_failure='tag contributes 0, no test catches it'`): the ~388 tag-keyed `Dictionary<string,...>` entries across `scripts/minigames/MinigameTagEffects.cs`, `SmithingMinigame.cs`, `RefiningMinigame.cs`, `EngineeringMinigame.cs`, `EnchantingMinigame.cs`; plus presentation mirrors `scripts/SkillVfx.cs:16-24` and `scripts/CombatWorld.cs:1002-1015`. **Largest silent-drift surface** — always surfaced by `blast_radius`.
- **Degradation:** without the .NET SDK, `CsExtractor` falls back to a regex/tree-sitter-c-sharp pass (finds `Dictionary` key literals and `== "x"` switches at lower precision).

### 3.4 `SchemaExtractor` — SQLite DDL (targets the four stores)

Parses `CREATE TABLE`/`INDEX`/`INSERT`/`SELECT` in `layer_store.py`, `stat_store.py`, `event_store.py`, `narrative_store.py`. Registers `db_column` concepts and one **`junction_shape`** concept per store capturing three divergent shapes:
- **split-column** `(tag_category, tag_value)` indexed on the pair, AND-match via `HAVING COUNT(DISTINCT tag_category || ':' || tag_value) >= ?` (`layer_store.py:271`, `stat_store.py`).
- **single-opaque** `(tag)` column, AND-match via N EXISTS subqueries (`event_store.py:81-87`, `narrative_store.py`).
- the **redundant `tags_json`-on-row** write path (`layer_store.py:137`) that must stay in sync.
- the `event_store.py` `SCHEMA_VERSION=2` hard gate.

### 3.5 `MlVocabExtractor` — frozen positional vocabularies

Reads the runtime encoder dicts (`systems/crafting_classifier.py`: `CATEGORY_TO_IDX`, `REFINEMENT_VOCAB`, `ELEMENT_HUES`/`CATEGORY_HUES`, engineering slot order) and ties each by `mirror_group` to the four duplicated CNN encoder copies and the LightGBM sorted-vocab builder. Each `ml_feature_slot` site carries `silent_failure='rename within count → column reads 0 / falls to hue 0'` vs the one hard failure (`count change → shape mismatch → validation silently skipped`, `crafting_classifier.py:974`). Records that **labels are binary valid/invalid, not tag-derived** so the assistant never forms the wrong "renaming a tag breaks a label vocab" model.

### 3.6 `JsonContentExtractor` — the ~4.8k JSON walk

Two modes over a **manifest of tag-bearing keys** (`tags`, `combatTags`, `effect_tags`, `effectTags`, `metadata.tags`, `context`):
- Every string in a tag-bearing array → a `json_value` site keyed to the concept whose value it equals, alias chain resolved at insert time.
- Marks sites from `items.JSON/`, `recipes.JSON/`, `Skills/`, `Definitions.JSON/`, `progression/` as **`editable=0, governance='content-frozen'`** (CLAUDE.md sacred boundary) so the assistant is steered to the *alias* fix.
- Records `NEGATIVE`: `placements.JSON/` files carry no `tags` keys — indexed as an asserted true-negative so counts aren't inflated.

### 3.7 `DbRowProbe` — live-DB read-only probe (Scenario 2 fix; **the decisive gap-closer**)

*Not a file walk.* Opens `world_memory.db` / `stat_store.db` / `event_store.db` / `narrative_store.db` **read-only** and, per concept, runs `SELECT COUNT(*)` on each junction for the `(tag_category,tag_value)` or opaque-tag match, plus the affected `tags_json` row count. Turns "the junction exists" into "**N historical rows in 4 stores need these 3 UPDATE shapes plus a tags_json rewrite**."

### 3.8 `PolyglotIndexer` + coverage self-check + `DriftDetector`

Orchestrates 3.1→3.7, then a post-pass writes `concept_edges`. A **coverage self-check** counts tag-keyed dicts / tag-bearing JSON keys per walk-root and *warns if a known-heavy file yields zero* (catches a stale walk manifest). `DriftDetector` materializes authority-vs-usage set-diffs (`used_but_undefined`, `defined_but_inert`, `dispatched_but_undefined`, `mirror_divergence`, `cross_taxonomy_twin`, `coverage_rot`). Everything is deterministic and side-effect-free, so CI can full-rebuild and diff against a committed index.

### 3.9 `McpSidecar`

The MCP server. NDJSON-over-stdio, reusing the exact protocol shape of `Game-1-Godot/sidecar/world_system_sidecar.py` (route library prints to stderr, reply JSON on a saved stdout handle, repo-root bootstrap). Read-only over `concern.db`; fans out to the composed LSP MCP for the symbol half and unions the results.

---

## 4. The MCP tool surface

Registered in `.claude/settings.json` `mcpServers`. Flagship is `concept_blast_radius`; the rest are drill-downs and safety/planning tools.

### `concept_blast_radius` — THE primary call (ranked, GROUPED)

```
concept_blast_radius(
  concept: str,                 # "fire", "single_target", "geometry", "monster_drop", "combatTags"
  taxonomy: str = "auto",
  include_symbolic: bool = true,# union in LSP find-references
  include_mirrors: bool = true,
  include_drift: bool = true,
  kinds: [str] = null           # filter to e.g. ["db_schema","ml_label"]
) -> {
  concept, taxonomy, authority_ref, resolved_aliases: [str],
  is_new: bool,                 # true if zero sites — triggers scaffold fallback
  nearest_siblings: [str],      # populated when is_new (Scenario 1 fix)
  groups: {                     # GROUPED by coupling_type so non-symbolic can't be missed
    symbolic:        [site],
    json_value:      [site],
    db_junction:     [site],
    ml_label:        [site],
    string_literal:  [site],
    csharp_mirror:   [site],
    output_contract: [site]
  },
  drift_concepts: [{concept, edge_kind, sites_count}],
  summary: {total, silent_sites, unguarded_mirror_sites, by_lang},
}
# each site = {file, line | db.table.column | model:slot, language, site_kind,
#              role, silent_failure, mirror_group, pinned_by_test, editable, rank}
```

Ranked by `calculate_relevance`-style overlap so **authority + dispatch + db_schema + ml_feature_slot + `silent_failure`-flagged** sites float to the top. **If `is_new` (empty result), it never returns a bare empty list** — it returns `nearest_siblings` and a `scaffold_hint`, so an empty radius never reads as "low blast radius."

### `concept_scaffold` — ADD playbook (Scenario 1 fix)

```
concept_scaffold(kind: str, name: str, taxonomy: str, sibling: str = null)
 -> { required_new_edits: [{file, line_anchor, site_kind, instruction, language}],
      retrain_required, db_migration_required, tests_to_add: [str] }
```

Clones the binding-site *shape* of a named sibling concept: every `site_kind` the sibling has becomes a REQUIRED-NEW-EDIT with the sibling's `file:line` as the "edit near here" anchor.

### `authority_of` — source of truth + legality

```
authority_of(concept: str)
 -> { concept, taxonomy, authority_ref, is_dynamic, allowed_values: [str], aliases: [str],
      defined_but_dead: [file:line],       # 'summon' TODO
      dead_but_dispatched: [file:line],    # 'blink'/'ethereal' aliases only
      shadow_warnings: [{other_taxonomy, note}] }  # combat 'element' vs WMS L1 'element'
```

### `mirror_check` — cross-language / cross-copy drift

```
mirror_check(concept: str = "", mirror_group: str = "")
 -> { groups: [{ mirror_group, purpose, members: [{file, line, language, content_hash}],
                 in_sync: bool, drifted_members: [file:line],
                 pinned_by: [test_file],
                 missing_obligations: [str] }] }   # e.g. "REQUIRED: add TagAttackTests golden"
```

Covers the py↔C# `EffectExecutor` pair, the 4 CNN encoder copies, the 3 hand-synced Godot tag→channel tables, and the parser↔`conformance/dump_databases.py:config_row`↔C# golden `pinned_by_golden` group. Reports *missing* obligations (an un-added golden fixture) as first-class items.

### `junction_map` — the db-junction specialist (+ row migration, Scenario 2 fix)

```
junction_map(concept: str = "tag", include_row_counts: bool = true)
 -> { stores: [{store, junction_table, shape: "split_column|single_opaque",
                and_match_semantics, redundant_row_store: bool,
                schema_version_gate: file:line,
                matching_row_count: int,          # from DbRowProbe
                tags_json_rows_affected: int,
                migration_sql_template: str }],    # paired junction + tags_json UPDATE
      divergences: [str],
      atomicity_warning: str }                     # "apply junction + tags_json together or desync"
```

### `ml_vocab_impact` — the ml-label specialist (+ artifact staleness, Scenario 2 fix)

```
ml_vocab_impact(concept: str)
 -> { is_ml_load_bearing, labels_are_binary: true,
      encoders: [{file, line, kind: "cnn_hue|cnn_shape|lgbm_positional|slot_onehot", role}],
      positional_risk, feature_count_effect: "none|shifts_count_crash|shifts_column_meaning",
      retrain_required,
      stale_artifacts: [{path, kind: "keras|lgbm_txt"}],  # frozen binaries invalidated by rename
      retrain_inputs: [str],                              # positive-example JSONs
      forward_warning: str }   # "not ML-load-bearing UNLESS a value lands on material metadata.tags"
```

### `reindex` — freshness on demand

```
reindex(paths: [str] = [], since_git_ref: str = "", probe_dbs: bool = false)
 -> { reindexed_files, concepts_touched, sites_updated, db_rows_reprobed, head_sha, stale_after }
```

### `open_site` — expand one site on demand

```
open_site(file: str, line: int, context_lines: int = 20)
 -> { file, line_start, line_end, code, neighbor_sites: [site] }
```

Keeps `blast_radius` payloads compact (locations only) while letting the assistant pull exact text for just the sites it will edit.

### The exact assistant workflow for a fundamental change

The MCP server's **tool descriptions instruct this sequence** so the assistant follows it without prompting:

- **Step 0 — Freshness.** `reindex(since_git_ref=<stored head>)` — cheap, per-file idempotent.
- **Step 1 — Blast radius (flagship).** `concept_blast_radius(concept)`. If `is_new` → Step 1a. Else read the **grouped** result; the `json_value`/`db_junction`/`ml_label`/`csharp_mirror` groups are the ones otherwise missed; `silent_sites`/`unguarded_mirror_sites` tell it where failure is quiet.
- **Step 1a (ADD only) — Scaffold.** `concept_scaffold(kind, name, taxonomy, sibling=<nearest_sibling>)`.
- **Step 2 — Authority & legality.** `authority_of(concept)`.
- **Step 3 — Specialist deep-dives** as indicated: `db_junction`→`junction_map`; `ml_label`→`ml_vocab_impact`; any `mirror_group`→`mirror_check`.
- **Step 4 — Edit**, guided by `authority_of` ordering (authority JSON → Python dispatch → C# mirror → each Godot table → ML encoder/retrain → junction DDL/version bump → golden fixture). `open_site` on demand.
- **Step 5 — Reindex + verify.** `reindex(paths=<edited>, probe_dbs=true)`, then re-run `mirror_check`/`junction_map` to confirm zero remaining old-value rows and in-sync mirrors.

---

## 5. Freshness / incremental re-index & drift detection

### Merkle-style incremental reindex

`index_meta(schema_version, repo_head_sha, indexed_at)` mirrors the `event_store.py SCHEMA_VERSION=2` hard-gate discipline: a schema bump forces a full rebuild. Per file we store a `content_hash`; per authority a hash.

- **On MCP startup / Step 0:** `reindex(since_git_ref=stored_head_sha)` → `git diff` yields the changed file set; delete each changed file's rows and re-extract. Cost is **O(changed files)**.
- **Authority files are invalidation roots.** A change to `tag-definitions.JSON`, `tag_library.py`, or `narrative-tag-definitions.JSON` re-runs `DriftDetector` *globally* for that taxonomy (cheap set-membership pass).
- **DB rows and model binaries are runtime state with no source delta.** `probe_dbs=true` on `reindex` (and Step-5 verify) re-runs `DbRowProbe`, closing the Scenario 2 freshness race.
- **Symbolic results are never cached** — fetched live from the LSP MCP.

### Drift detection between the parallel vocabularies

| Finding | Example (grounded) | Detection |
|---|---|---|
| `used_but_undefined` | `skills-skills-1.JSON` uses `single`; authority has only `single_target` | content value ∉ (authority ∪ aliases) |
| `defined_but_inert` | `summon` in `tag-definitions.JSON`, only a TODO at `effect_executor.py:253` | authority value with no dispatch site |
| `dispatched_but_undefined` | `blink`/`ethereal` handled in `effect_executor.py` but not JSON | dispatch literal with no authority value & no alias |
| `mirror_divergence` | a special tag in `effect_executor.py` missing from `EffectExecutor.cs` | `mirror_group` member set mismatch by `content_hash` |
| `cross_taxonomy_twin` | WMS `element:ice` vs combat `damage_type:frost` | value in one taxonomy's frozenset absent from another → candidate un-seeded `drifts_from` |
| `coverage_rot` | a tag with no prompt fragment / no minigame-table entry | `FRAGMENT_CATEGORIES`/minigame-table membership diff |

The `cross_taxonomy_twin` self-check compensates for the honest limitation that `drifts_from` recall depends on the hand-seeded set — it *flags candidates* even for un-catalogued divergences.

---

## 6. Build plan in phases

**Phase 1 — Highest-frequency value, ~1.5 days (json-value + authority + flagship spine).**
`ConceptStore` (near-verbatim copy of `layer_store.py` junction + `tag_relevance.py` scoring), `McpSidecar` shell (copy `world_system_sidecar.py` protocol), `VocabularyExtractor` (tag-definitions.JSON + tag_library.py recipes), `JsonContentExtractor`, first-cut `PyExtractor` (dispatch/category literals). Ships `concept_blast_radius` + `authority_of` end-to-end.

**Phase 2 — Two hardest non-symbolic couplings, ~1 day.**
`SchemaExtractor` + `MlVocabExtractor` + `DbRowProbe` + `drifts_from`/`shadows` seed edges. Ships `junction_map` (row migration) + `ml_vocab_impact` (artifact staleness). Closes Scenario 2.

**Phase 3 — Cross-language + drift + freshness, ~1 day.**
`CsExtractor` (Roslyn) with `mirror_group` pairing, `mirror_check`, `DriftDetector`, incremental `reindex`, coverage self-check. Closes py↔C# + unmirrored-Godot-table gaps.

**Phase 4 (optional) — Add-flows + structural refactor support.**
`concept_scaffold`, `output_contract_field` kind + attribute visitors, `category_requires`/`ordering_invariant`/`pinned_by_golden` edges. Closes Scenarios 1 & 3.

**Phase 5 (optional) — LSP composition.**
Wire the off-the-shelf LSP MCP into `include_symbolic`. Until then, `blast_radius` returns the overlay only and tells the assistant to fall back to raw find-references for pure symbolic refactors.

**Long-tail:** curate the `drifts_from`/`alias` seed set and the tag-bearing-JSON-key + walk-root manifests; the coverage self-check flags when a manifest is stale.

Load-bearing pieces (junction schema, intersection query, relevance scoring, NDJSON protocol) are copies of *tested repo code*, so a working v1 (Phases 1–3) is ~3 focused days.

---

## 7. Honest tradeoffs, failure modes & non-goals

- **Extraction is heuristic, not a proof.** Extractors recognize *patterns* (literal-in-comparison, dict-key literal, `.get(literal)`). A tag built by runtime concatenation, read from env, or dispatched through a novel idiom is missed until a visitor is added. Mitigation: additive extractors; CI full-rebuild diff; coverage self-check. **Never present the tool as exhaustive-by-proof** — its own descriptions say so.
- **No embeddings → exact-string + curated edges.** A brand-new *un-catalogued* drift won't auto-link (the `cross_taxonomy_twin` self-check flags candidates). Deliberate trade: recall for novel synonyms swapped for zero-infra determinism.
- **Complements, does not replace, the symbol layer for structural refactors.** A parser-logic refactor's true blast radius is the `EffectConfig` field contract + `parse()` call-sites. Phase 4's `output_contract_field` visitor + the composed LSP cover this; *without them the registry regresses vs a plain call-graph on symbolic refactors.* The workflow tells the assistant to drive structural refactors with find-references and use the registry as complement.
- **`mirror_check` is a high-recall drift alarm, not a semantic equivalence checker.** `content_hash` detects that two mirrors *differ*, not whether the difference is benign. The `ordering_invariant` edge surfaces the base-damage/synergy caveat as a *caveat to open-and-verify*, not an automated proof.
- **The index is derived state; freshness is a contract.** Between an edit and a `reindex` the map can be stale; DB-row/model-binary state has no source delta. Step 0 and Step 5 (`probe_dbs=true` + verify) make freshness explicit; a Claude Code `PostToolUse` hook can auto-run `reindex` on touched paths — but the guarantee relies on honoring it.
- **Content-JSON governance is surfaced, not enforced.** Content tag arrays are OFF-LIMITS per CLAUDE.md; the registry marks those sites `editable=0, governance='content-frozen'` and steers to the *alias* fix, but a human ratifies boundary-crossing edits.

**Deliberate non-goals:** GDScript (no tooling; game logic is C#, so nothing load-bearing lost — `.gd`-touching concepts get a coverage-gap marker, never silent omission); semantic/fuzzy concerns (must resolve to a concept id); runtime save-data values beyond migration counts; auto-fixing (the registry surfaces and plans; the assistant performs the synchronized edit).

---

## 8. Off-the-shelf reuse vs the custom piece

**Compose off-the-shelf (zero custom code):**
- **An LSP-backed symbol MCP** (e.g. Serena, or any `find_symbol`/`find_referencing_symbols` server) with pyright/jedi over `Game-1-modular/` and OmniSharp/Roslyn over `Game-1-Godot/src`. This is the *entire symbolic half*. **Own the C#-LSP-flaky degradation:** if the C# server is unavailable, `include_symbolic` returns Python-only and the overlay still delivers vocabulary/mirror/table/junction/ML couplings natively — degrade to a *subset*, never to nothing. Never cache symbolic results, so LSP freshness is never *our* stale state.
- **tree-sitter grammars** (python, c-sharp, json) for precise string-literal offsets — used inside the extractors, and as the `CsExtractor` regex-fallback when the .NET SDK is absent.

**The custom piece (~3 days for v1) reuses the repo's own verified substrate:**

| Custom component | Reuses (verbatim or near-) |
|---|---|
| `ConceptStore` junction + `query_binding_sites` | `world_system/world_memory/layer_store.py` split-column schema + `(cat,val)` index + `HAVING COUNT(DISTINCT ...)` intersection (`layer_store.py:271`) |
| `rank_related` overlap ranking | `world_system/world_memory/tag_relevance.py:53-57` (exact=1.0, same-category=0.3, normalized) |
| `authority_of` allowed-values / is_dynamic | `world_system/world_memory/tag_library.py` `validate_tag`/`render_assignable_tag_allowlist` (parsed, not imported, on the hot path) |
| `McpSidecar` NDJSON-over-stdio + stdout-purity | `Game-1-Godot/sidecar/world_system_sidecar.py` |
| Python-sidecar-reusing-core precedent | `Game-1-Godot/sidecar/invention_sidecar.py` |
| single-physical-`tag-definitions.JSON` cross-language insight | `Game-1-Godot/src/Game1.Core/Content/ContentPaths.cs` (ADR-4) — the C# port reads Python's own JSON, so tag *vocabulary* is single-sourced; only *dispatch* drifts |
| `index_meta.schema_version` full-rebuild gate | `event_store.py SCHEMA_VERSION=2` discipline |

**Net:** small custom code (five extractors + a DB-row probe + a thin SQLite-backed MCP), near-copies of trusted code, capturing exactly the three non-symbolic coupling classes (`json-value`, `db-junction`, `ml-label`) plus `csharp-mirror` and `output-contract` surfaces a generic call-graph MCP is structurally blind to. The flagship `concept_blast_radius` returns them **grouped, ranked, with `silent_failure` annotations in one call** — so a fundamental tag change arrives as openable `file:line` / `db.table.column` / `model:slot` handles, and nothing escapes the context window.

---

## Appendix A — Adversarial verify findings (the three change scenarios)

Each scenario initially returned **"gaps"**; the fixes above are the closure. Retained for revival so the reasoning isn't lost.

**Scenario 1 — ADD a new tag category `element_resonance`.** Gap: an empty `blast_radius` reads as "low risk"; a net-new category has no existing usage to find. Fixes: `concept_scaffold` (clone a sibling's site shape), `is_new`+`nearest_siblings` fallback, `category_requires` edge, the "new category dropped with NO warning" annotation on the parser bucket-chain, a config-field obligation, a shared `element_palette_family` VFX mirror_group, and a forward-warning about future ML coupling.

**Scenario 2 — RENAME/RETIRE an element value used in combat + WMS SQLite + CNN label.** Decisive gap: *existing DB rows and frozen model binaries are runtime state no source walk sees.* Fixes: `DbRowProbe` (live read-only row counts + migration templates), paired junction+`tags_json` atomic UPDATE, `ml_vocab_impact` artifact-staleness reporting, seeded `drifts_from` for `ice↔frost`/`single↔single_target`/`poison↔poison_status`, content-frozen governance flag steering to alias, and a post-migration verification re-probe.

**Scenario 3 — CHANGE the tag PARSING logic (structural refactor).** Gap: the true blast radius is the `EffectConfig` *field contract* (symbolic attribute access) + `parse()` call-sites, which the string extractors miss — a regression vs a plain call-graph. Fixes: `output_contract_field` concept kind + attribute-access visitors, register the conformance oracle (`conformance/dump_databases.py:config_row`) + C# golden tests as a `pinned_by_golden` mirror group, `ordering_invariant` edge for the base-damage/synergy caveat, and the explicit rule that structural refactors are LSP-driven with the registry as complement.

---

## Appendix B — File map & seams (build reference)

Reference implementations to copy from (verify line numbers at build time — they drift):
- `Game-1-modular/world_system/world_memory/layer_store.py` — junction schema + intersection query (the `ConceptStore` template)
- `Game-1-modular/world_system/world_memory/tag_relevance.py` — `calculate_relevance` overlap scoring
- `Game-1-modular/world_system/world_memory/tag_library.py` — authority taxonomy + `validate_tag` + allow-list render
- `Game-1-modular/Definitions.JSON/tag-definitions.JSON` — combat taxonomy authority
- `Game-1-modular/core/tag_parser.py` — category bucket chain (parser sites)
- `Game-1-modular/core/effect_executor.py` — special-tag dispatch chain + `EffectConfig` reads
- `Game-1-Godot/sidecar/world_system_sidecar.py` — NDJSON-over-stdio MCP protocol (the `McpSidecar` template)
- `Game-1-Godot/sidecar/invention_sidecar.py` — Python-sidecar-reusing-Core precedent

Proposed home for the new system: `Game-1-modular/tools/concern_mcp/` (Python, reuses stdlib `sqlite3`, no new deps for Phases 1–2; Roslyn/tree-sitter added in Phase 3).
