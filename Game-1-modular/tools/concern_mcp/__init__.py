"""Concern-Registry MCP for Game-1.

A code-concern memory layer that surfaces the COMPLETE, grounded blast radius of a
cross-cutting concept (a tag value / category / param-key) across the scattered web
of couplings that a symbol/call-graph is structurally blind to: json-value,
db-junction, ml-label, csharp-mirror, and string-literal dispatch.

Design + rationale: Development-Plan/MEMORY_RETRIEVAL_MCP.md
Backbone reuses the repo's own WMS tag-indexed SQLite substrate
(world_system/world_memory/layer_store.py + tag_relevance.py).

Phase 1 (this package): ConceptStore + VocabularyExtractor + JsonContentExtractor +
PyExtractor + PolyglotIndexer + queries (concept_blast_radius, authority_of) +
a minimal MCP stdio server and a CLI verification harness.

Zero third-party dependencies -- stdlib only (sqlite3, ast, json, hashlib, glob, re).
"""

from .store import ConceptStore, SCHEMA_VERSION  # noqa: F401

__all__ = ["ConceptStore", "SCHEMA_VERSION"]
