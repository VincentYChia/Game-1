"""CLI harness for the concern registry -- verify the whole pipeline without Claude Code.

  python -m tools.concern_mcp.cli build [--verbose]      # (re)build the index over the repo
  python -m tools.concern_mcp.cli blast fire             # flagship blast-radius, human-readable
  python -m tools.concern_mcp.cli authority lifesteal    # source of truth + hazards
  python -m tools.concern_mcp.cli stats                  # index size
  python -m tools.concern_mcp.cli reindex core/tag_parser.py ...   # incremental

Run from Game-1-modular/ (so `tools.concern_mcp` resolves), or from anywhere with -m.
"""

from __future__ import annotations

import argparse
import json
import sys

from .paths import REPO_ROOT, SCAN_ROOT, DEFAULT_DB
from .store import ConceptStore
from .indexer import PolyglotIndexer
from . import queries


def _store(db: str) -> ConceptStore:
    return ConceptStore(db)


def cmd_build(args) -> int:
    store = _store(args.db)
    idx = PolyglotIndexer(REPO_ROOT, SCAN_ROOT)
    stats = idx.build(store, verbose=args.verbose)
    print(f"Built index -> {args.db}")
    print(f"  concepts={stats['concepts']}  binding_sites={stats['binding_sites']}  "
          f"edges={stats['concept_edges']}  files={stats['indexed_files']}  "
          f"({stats['elapsed_ms']} ms)")
    store.close()
    return 0


def cmd_reindex(args) -> int:
    store = _store(args.db)
    idx = PolyglotIndexer(REPO_ROOT, SCAN_ROOT)
    res = idx.reindex(store, args.paths)
    print(json.dumps(res))
    store.close()
    return 0


def cmd_stats(args) -> int:
    store = _store(args.db)
    print(json.dumps(store.stats(), indent=2))
    store.close()
    return 0


def cmd_blast(args) -> int:
    store = _store(args.db)
    res = queries.concept_blast_radius(store, args.concept, taxonomy=args.taxonomy)
    if args.json:
        print(json.dumps(res, indent=2))
        store.close()
        return 0
    _print_blast(res)
    store.close()
    return 0


def cmd_authority(args) -> int:
    store = _store(args.db)
    res = queries.authority_of(store, args.concept, taxonomy=args.taxonomy)
    print(json.dumps(res, indent=2))
    store.close()
    return 0


def _print_blast(res: dict) -> None:
    c = res.get("concept")
    if res.get("is_new"):
        print(f"## {c}: NO binding sites (is_new -- treat as ADD)")
        print(f"  hint: {res.get('scaffold_hint')}")
        print(f"  sibling categories: {', '.join(res.get('nearest_siblings', []))}")
        return
    s = res["summary"]
    print(f"## BLAST RADIUS: {c}   taxonomies={res.get('taxonomies')}")
    print(f"  authority: {res.get('authority_ref')}")
    if res.get("resolved_aliases"):
        print(f"  aliases: {res['resolved_aliases']}")
    if res.get("shadow_warning"):
        print(f"  [!] {res['shadow_warning']}")
    print(f"  total sites={s['total']}  silent-failure sites={s['silent_sites']}  "
          f"by-lang={s['by_lang']}")
    order = ["authority", "symbolic", "output_contract", "code_dispatch", "db_junction",
             "ml_label", "csharp_mirror", "json_value", "vfx", "test", "other"]
    groups = res["groups"]
    for g in order:
        if g not in groups:
            continue
        sites = groups[g]
        print(f"\n  -- {g}  ({len(sites)}) --")
        for st in sites[:40]:
            sf = f"   [!] {st['silent_failure']}" if st.get("silent_failure") else ""
            lock = " [frozen]" if not st.get("editable", True) else ""
            print(f"    [{st['rank']:>3}] {st['loc']}{lock}  -- {st['role']}{sf}")
        if len(sites) > 40:
            print(f"    ... +{len(sites) - 40} more")
    if res.get("related_concepts"):
        rel = ", ".join(f"{r['concept']}({r['edge_kind']})" for r in res["related_concepts"][:12])
        print(f"\n  related: {rel}")


def main(argv=None) -> int:
    try:  # Windows consoles default to cp1252; keep output robust to any glyph.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    p = argparse.ArgumentParser(prog="concern_mcp.cli")
    p.add_argument("--db", default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build"); b.add_argument("--verbose", action="store_true")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("reindex"); r.add_argument("paths", nargs="+")
    r.set_defaults(func=cmd_reindex)

    sub.add_parser("stats").set_defaults(func=cmd_stats)

    bl = sub.add_parser("blast")
    bl.add_argument("concept")
    bl.add_argument("--taxonomy", default="auto")
    bl.add_argument("--json", action="store_true")
    bl.set_defaults(func=cmd_blast)

    au = sub.add_parser("authority")
    au.add_argument("concept")
    au.add_argument("--taxonomy", default="auto")
    au.set_defaults(func=cmd_authority)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
