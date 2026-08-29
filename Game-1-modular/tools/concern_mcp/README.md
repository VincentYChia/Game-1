# Concern-Registry MCP (Phases 1–5, complete)

A code-concern memory layer for Game-1. It answers one question well:

> **"Before I fundamentally change concept X (a tag), show me the COMPLETE, grounded blast radius so nothing escapes the context window."**

Tags couple through this repo in ways a symbol/call-graph is structurally blind to — a
tag value like `fire` lives in **JSON content values**, **SQLite tag-junction rows**,
**CNN/LightGBM label tables**, the **C# port**, and **VFX branches**, none referencing
each other symbolically, all failing **silently** on a rename. This registry indexes the
*concept* (not the file/symbol) and returns every binding site as an openable
`file:line` with a note on how it fails silently.

Full design + rationale: [`Development-Plan/MEMORY_RETRIEVAL_MCP.md`](../../../Development-Plan/MEMORY_RETRIEVAL_MCP.md).

---

## Quick start (CLI — no Claude Code needed)

```bash
cd Game-1-modular
python -m tools.concern_mcp.cli build --verbose        # (re)build the index (~1s)
python -m tools.concern_mcp.cli blast fire             # flagship: grouped blast radius
python -m tools.concern_mcp.cli blast lifesteal        # shows dispatch + aliases
python -m tools.concern_mcp.cli authority lifesteal    # source of truth + siblings + hazards
python -m tools.concern_mcp.cli blast fire --json      # machine-readable
python -m tools.concern_mcp.cli reindex core/tag_parser.py   # incremental after edits
python -m tools.concern_mcp.cli stats
```

Example (`blast fire`) surfaces, in one call: the authority in **both** taxonomies
(`tag-definitions.JSON` + WMS `tag_library.py`), the CNN hue table
(`crafting_classifier.py`), three VFX color tables, ~40 content-JSON sites (marked
`[frozen]` per CLAUDE.md), and a **shadow warning** that combat-`fire` and WMS-`fire`
are separate vocabularies.

## Register in Claude Code (MCP)

A portable, committed `.mcp.json` lives at the **repo root** (`Game-1/.mcp.json`):

```json
{
  "mcpServers": {
    "concern-registry": {
      "command": "py",
      "args": [
        "-3",
        "-c",
        "import sys,os;root=os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd();sys.path.insert(0,os.path.join(root,'Game-1-modular'));from tools.concern_mcp.server import main;main()"
      ],
      "timeout": 30000
    }
  }
}
```

Portable by design, and hardened against two real Windows failure modes discovered in
testing:
- **`py -3`** (the Windows Python launcher) instead of bare `python` — avoids the Microsoft
  Store `python.exe` stub, which starts and immediately exits (→ `-32000 Connection closed`).
- **Self-locates via the `CLAUDE_PROJECT_DIR` *environment variable* at runtime**, not JSON
  `${...}` substitution. Claude Code does NOT expand `${CLAUDE_PROJECT_DIR}` inside a
  `PYTHONPATH` value (that leaves the literal string → `ModuleNotFoundError: tools` → the
  process exits → connection closed). Reading the env var inside a tiny `-c` bootstrap
  sidesteps that entirely and needs no `env` block, no absolute paths, no username.

The server is **stdlib-only**, so any Python 3.8+ works. (Non-Windows: swap `command` to
`python3` and drop the `-3` arg.)

**Activate (a `.mcp.json` is read only at session start):**
1. **Restart** the Claude Code session (close/reopen the panel, or reload the VS Code window).
   In the VS Code extension your conversation is preserved — resume it from the session-history panel.
2. **Approve** the project-server trust dialog when it appears.
3. **Verify** with `/mcp` — `concern-registry` should show ✔ Connected with 9 tools.

**New device:** clone the repo → ensure `python --version` (3.8+) resolves in the VS Code
integrated terminal → open the project in Claude Code → approve on first `/mcp`. No build
step needed (the index builds itself on first tool call). If `/mcp` shows a launch error,
`python` isn't on PATH for the subprocess — set `command` to an absolute interpreter path
(e.g. `.venv/Scripts/python.exe`; `${CLAUDE_PROJECT_DIR}` does NOT expand in `command`).

The server builds the index lazily on first call. Tools exposed:

| Tool | Purpose |
|---|---|
| `concept_blast_radius(concept, taxonomy?, kinds?, include_symbolic?)` | **Flagship.** Grouped, ranked blast radius (authority / symbolic / output_contract / code_dispatch / db_junction / ml_label / csharp_mirror / json_value / vfx) with `silent_failure` notes + `next_tools`. |
| `authority_of(concept, taxonomy?)` | Source of truth, legal sibling values, aliases, governance, shadow/dead hazards. |
| `junction_map(concept)` | **Live** SQLite row counts + migration SQL across the 4 WMS/WNS `.db` files (read-only). |
| `ml_vocab_impact(concept)` | CNN/LightGBM encoder refs, duplicated training mirrors, STALE model artifacts, count-sensitivity. |
| `mirror_check(concept, mirror_group?)` | py↔C# mirror alignment, unguarded Godot tables, golden regeneration obligation. |
| `concept_scaffold(kind, name, sibling?)` | ADD playbook: category structural sites, or clone a sibling value's site shape. |
| `drift_report()` | used/dispatched-but-undefined, defined-but-inert, cross-taxonomy twins, unmirrored Godot count. |
| `concern_reindex(paths?)` | Refresh after edits (paths = incremental; empty = full rebuild). |
| `concern_stats()` | Index size / freshness / coverage warnings. |

Protocol smoke test (no Claude Code): `python -m tools.concern_mcp.server --selftest`

## The intended assistant workflow for a fundamental change

0. `concern_reindex` (freshness) → 1. `concept_blast_radius` (read the grouped result;
`json_value`/`db_junction`/`ml_label`/`vfx` are the groups you'd otherwise miss) →
2. `authority_of` (edit order + hazards) → 3. open the specific sites you'll edit →
4. edit authority → dispatch → mirrors → content(alias) → 5. `concern_reindex` + re-check.

## What's covered (Phases 1–5, all built)

- **Phase 1 — vocabulary + json + code:** combat-effect + WMS tag authorities, json-value
  coupling across content JSON, Python string-literal couplings (dispatch `==` branches,
  category branches, dict-key palette/label tables, `.get('combatTags')`), alias resolution,
  shadow warnings, used/dispatched-but-undefined drift, incremental reindex.
- **Phase 2 — DB + ML:** `SchemaExtractor` (both junction shapes across 4 stores),
  `DbRowProbe` (live read-only row counts + migration SQL against the real `.db` files),
  `MlVocabExtractor` (CNN/LightGBM encoders, duplicated training mirrors, baked artifacts,
  count-sensitivity) → `junction_map` / `ml_vocab_impact`.
- **Phase 3 — C# + drift:** `CsExtractor` (7 curated golden-pinned core mirrors + regex-scanned
  ~33 unmirrored Godot tables), `mirror_check`, `DriftDetector`, coverage self-check.
- **Phase 4 — contract + scaffold:** `output_contract_field` (the EffectConfig 13-field
  contract + 4 lockstep serializers + base-damage-before-synergies ordering invariant),
  `concept_scaffold` (category + value ADD playbooks).
- **Phase 5 — symbolic hook:** `include_symbolic` composes an LSP provider via
  `CONCERN_SYMBOLIC_CMD`, degrading to curated find-references anchors when none is set.

All grounded coordinates live in `coordinates.py`, verified against current source; the
coverage self-check warns if any curated location goes stale (yields zero sites).

**Deliberate non-goals:** GDScript; semantic/fuzzy concept lookup; auto-fixing. The tool
surfaces and plans; you perform the synchronized edit. It is **not exhaustive-by-proof** —
source extraction is pattern-based (a runtime-concatenated tag string is missed until a
visitor is added), so it complements — not replaces — an LSP for pure symbolic refactors.

## Tests

```bash
cd Game-1-modular && python -m pytest tools/concern_mcp/tests -q
```

Self-contained (synthetic mini-repo in tmp) — fast, no dependence on the full tree.

## Layout

```
tools/concern_mcp/
├── store.py            ConceptStore — SQLite substrate (mirrors WMS layer_store + tag_relevance)
├── indexer.py          PolyglotIndexer — orchestration + incremental reindex + coverage check
├── queries.py          blast_radius, authority_of, junction_map, ml_vocab_impact,
│                       mirror_check, concept_scaffold, drift_report
├── coordinates.py      grounded constant tables (junctions, encoders, C# mirrors, contract)
├── seeds.py            curated drift-twin (drifts_from) seed edges
├── drift.py            DriftDetector + coverage self-check
├── symbolic.py         Phase 5 LSP-composition hook (CONCERN_SYMBOLIC_CMD, graceful degrade)
├── server.py           MCP stdio JSON-RPC server (9 tools)
├── cli.py              CLI verification harness
├── paths.py / util.py  path resolution + file walking / hashing / encoding-tolerant read
├── extractors/
│   ├── vocabulary.py   authorities: tag-definitions.JSON + tag_library.py (ast) + load_vocab
│   ├── json_content.py tag-bearing content-JSON line scanner
│   ├── py_dispatch.py  Python ast: dispatch / category / dict-key / param-key sites
│   ├── schema.py       SchemaExtractor — SQLite junction db_schema sites
│   ├── ml_vocab.py     MlVocabExtractor — CNN/LightGBM encoder ml_label sites
│   ├── db_probe.py     DbRowProbe — live read-only row counts (query-time)
│   ├── csharp.py       CsExtractor — curated core mirrors + regex Godot tables
│   └── contract.py     ContractExtractor — EffectConfig output_contract sites
└── tests/test_registry.py   (19 tests)
```
