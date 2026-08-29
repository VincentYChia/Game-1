#!/usr/bin/env python3
"""Concern-Registry MCP server -- stdio JSON-RPC 2.0 for Claude Code.

Exposes the concern registry as MCP tools so the assistant can pull the COMPLETE,
grounded blast radius of a cross-cutting concept (a tag value / category) before a
fundamental change -- the json-value / db / ml / vfx couplings a call-graph misses.

Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout (the MCP stdio transport).
Like Game-1-Godot/sidecar/world_system_sidecar.py, stdout is kept PURE for protocol
frames -- any stray library print is routed to stderr.

Register in Claude Code (project .mcp.json or user settings), e.g.:

  {
    "mcpServers": {
      "concern-registry": {
        "command": "python",
        "args": ["-m", "tools.concern_mcp.server"],
        "cwd": "<repo>/Game-1-modular"
      }
    }
  }

Run standalone for a protocol smoke test:  python -m tools.concern_mcp.server --selftest
"""

from __future__ import annotations

import json
import sys

# Keep STDOUT pure for JSON-RPC frames; route any library prints to stderr.
_OUT = sys.stdout
sys.stdout = sys.stderr

from .paths import REPO_ROOT, SCAN_ROOT, DEFAULT_DB  # noqa: E402
from .store import ConceptStore  # noqa: E402
from .indexer import PolyglotIndexer  # noqa: E402
from . import queries  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "concern-registry", "version": "0.1.0"}

_state = {"store": None, "indexer": None}


def _store() -> ConceptStore:
    if _state["store"] is None:
        st = ConceptStore(DEFAULT_DB)
        _state["store"] = st
        _state["indexer"] = PolyglotIndexer(REPO_ROOT, SCAN_ROOT)
        if st.stats()["concepts"] == 0:  # first run -- build lazily
            _state["indexer"].build(st)
    return _state["store"]


# ── tool registry ─────────────────────────────────────────────────
TOOLS = [
    {
        "name": "concept_blast_radius",
        "description": (
            "THE primary tool. Return the COMPLETE, grounded, ranked blast radius of a "
            "cross-cutting concept (a tag value like 'fire'/'lifesteal', a category like "
            "'geometry', or a param-key like 'combatTags') BEFORE changing it. Results are "
            "GROUPED by coupling type (authority / code_dispatch / json_value / vfx / "
            "db_junction / ml_label / csharp_mirror) so the non-symbolic couplings a "
            "call-graph misses cannot be overlooked; each site is an openable file:line with "
            "a 'silent_failure' note (what breaks with NO error on rename). ALWAYS call this "
            "first when asked to fundamentally change the tag system or any scattered concept. "
            "Then call authority_of for the edit order, and open_site/Read the specific sites "
            "you will edit. If is_new=true, treat it as an ADD (see nearest_siblings)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {"type": "string", "description": "tag value / category / param-key"},
                "taxonomy": {"type": "string", "default": "auto",
                             "description": "auto | combat_effect | wms | wns"},
                "kinds": {"type": "array", "items": {"type": "string"},
                          "description": "optional group filter, e.g. ['json_value','ml_label']"},
            },
            "required": ["concept"],
        },
    },
    {
        "name": "authority_of",
        "description": (
            "The source-of-truth for a concept: where it is defined (authority_ref), the legal "
            "sibling values in its category, aliases, whether the category is dynamic, content "
            "governance (is the authority a CLAUDE.md-frozen JSON?), and hazards "
            "(shadow_warnings for same-string-different-taxonomy; dead_but_dispatched; "
            "possibly_inert). Call after concept_blast_radius to decide WHERE to edit first."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {"type": "string"},
                "taxonomy": {"type": "string", "default": "auto"},
            },
            "required": ["concept"],
        },
    },
    {
        "name": "junction_map",
        "description": (
            "SQLite tag-junction migration plan for a value: opens the 4 real WMS/WNS .db files "
            "READ-ONLY and returns matching junction-row counts + tags_json counts + a migration "
            "SQL template per store (two shapes: split-column vs single-opaque). Call when "
            "blast_radius shows a db_junction group and you're renaming/retiring a value -- source "
            "edits alone leave STALE ROWS."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept": {"type": "string"},
                "include_row_counts": {"type": "boolean", "default": True},
            },
            "required": ["concept"],
        },
    },
    {
        "name": "ml_vocab_impact",
        "description": (
            "ML retrain scope + STALE model-artifact report for a value: which CNN/LightGBM "
            "encoders reference it, the duplicated training mirrors, the baked .keras/.txt "
            "artifacts invalidated by a rename, and whether it's count-sensitive (feature-shape "
            "guard). Labels are binary valid/invalid, NOT tag-derived. Call when blast_radius "
            "shows an ml_label group."),
        "inputSchema": {"type": "object", "properties": {"concept": {"type": "string"}}, "required": ["concept"]},
    },
    {
        "name": "mirror_check",
        "description": (
            "py<->C# mirror alignment for a concept (or a mirror_group): the paired sites, whether "
            "a golden test pins them, the UNGUARDED Godot minigame tables (no test), and the golden "
            "regeneration obligation. Call when blast_radius shows a csharp_mirror group."),
        "inputSchema": {
            "type": "object",
            "properties": {"concept": {"type": "string"}, "mirror_group": {"type": "string"}},
        },
    },
    {
        "name": "concept_scaffold",
        "description": (
            "ADD playbook. For kind='category': the fixed structural sites a NEW category needs "
            "(parser branch, EffectConfig field x2 languages, C# switch, golden). For "
            "kind='tag_value': clones the binding-site SHAPE of a sibling value into required-new-"
            "edits. Call when blast_radius returns is_new=true (an ADD, not a change)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "category | tag_value"},
                "name": {"type": "string"},
                "taxonomy": {"type": "string", "default": "combat_effect"},
                "sibling": {"type": "string", "description": "for tag_value: an existing value to clone"},
            },
            "required": ["kind", "name"],
        },
    },
    {
        "name": "drift_report",
        "description": (
            "Repo-wide drift findings: used-but-undefined, dispatched-but-undefined, "
            "defined-but-inert (combat), cross-taxonomy twins, and the count of unmirrored Godot "
            "tag sites. The authority-vs-usage set-diffs that fail silently in the running game."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "concern_reindex",
        "description": (
            "Refresh the index. Pass 'paths' (repo-relative) to re-extract just those files "
            "after edits; pass nothing to full-rebuild. Call after editing tag sites so the map "
            "reflects your changes (source layer; DB rows re-probe live via junction_map)."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}, "default": []},
            },
        },
    },
    {
        "name": "concern_stats",
        "description": "Index size / freshness (concepts, binding_sites, edges, indexed files, head sha, coverage warnings).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _call_tool(name: str, args: dict) -> dict:
    st = _store()
    if name == "concept_blast_radius":
        return queries.concept_blast_radius(
            st, args["concept"], taxonomy=args.get("taxonomy", "auto"),
            kinds=args.get("kinds"), include_symbolic=args.get("include_symbolic", True))
    if name == "authority_of":
        return queries.authority_of(st, args["concept"], taxonomy=args.get("taxonomy", "auto"))
    if name == "junction_map":
        return queries.junction_map(st, args["concept"], args.get("include_row_counts", True))
    if name == "ml_vocab_impact":
        return queries.ml_vocab_impact(st, args["concept"])
    if name == "mirror_check":
        return queries.mirror_check(st, args.get("concept", ""), args.get("mirror_group", ""))
    if name == "concept_scaffold":
        return queries.concept_scaffold(st, args["kind"], args["name"],
                                        args.get("taxonomy", "combat_effect"), args.get("sibling"))
    if name == "drift_report":
        return queries.drift_report(st)
    if name == "concern_reindex":
        paths = args.get("paths") or []
        if paths:
            return _state["indexer"].reindex(st, paths)
        return _state["indexer"].build(st)
    if name == "concern_stats":
        s = st.stats()
        s["repo_head_sha"] = st.get_meta("repo_head_sha")
        s["built_at"] = st.get_meta("built_at")
        return s
    raise ValueError(f"unknown tool: {name}")


# ── JSON-RPC plumbing ─────────────────────────────────────────────
def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle(req):
    """Return a response dict, or None for notifications (no id)."""
    method = req.get("method")
    req_id = req.get("id")
    is_notification = "id" not in req

    if method == "initialize":
        return _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = _call_tool(name, args)
            text = json.dumps(result, indent=2)  # ensure_ascii keeps stdio 7-bit safe
            return _result(req_id, {"content": [{"type": "text", "text": text}],
                                    "isError": False})
        except Exception as e:  # noqa: BLE001 -- surface tool errors as MCP tool errors
            return _result(req_id, {
                "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                "isError": True})

    if is_notification:
        return None
    return _error(req_id, -32601, f"method not found: {method}")


def _send(msg):
    _OUT.write(json.dumps(msg) + "\n")
    _OUT.flush()


def main():
    for line in sys.stdin:
        line = line.strip().lstrip("﻿").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            resp = _handle(req)
        except Exception as e:  # noqa: BLE001
            resp = _error(req.get("id"), -32603, f"{type(e).__name__}: {e}")
        if resp is not None:
            _send(resp)


def _selftest():
    """Drive the protocol over an in-process pipe (no Claude Code needed)."""
    for msg in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "concept_blast_radius", "arguments": {"concept": "fire"}}},
    ):
        resp = _handle(msg)
        if msg["method"] == "tools/call":
            payload = json.loads(resp["result"]["content"][0]["text"])
            print(f"[selftest] blast fire -> total={payload['summary']['total']} "
                  f"groups={payload['summary']['group_counts']}", file=sys.stderr)
        else:
            keys = list(resp["result"].keys())
            print(f"[selftest] {msg['method']} -> ok ({keys})", file=sys.stderr)
    print("[selftest] PASS", file=sys.stderr)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
