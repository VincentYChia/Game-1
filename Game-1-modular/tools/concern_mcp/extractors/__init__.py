"""Extractors that populate the concern registry from the repo's real sources.

Phase 1:
- VocabularyExtractor -- authorities first (tag-definitions.JSON + tag_library.py)
- JsonContentExtractor -- the tag-bearing content JSON surface (json-value coupling)
- PyExtractor -- Python string-literal dispatch / category / dict-key / param-key sites

Later phases add SchemaExtractor, MlVocabExtractor, DbRowProbe, CsExtractor (see
Development-Plan/MEMORY_RETRIEVAL_MCP.md §3).
"""

from .vocabulary import VocabularyExtractor, VocabResult  # noqa: F401
from .json_content import JsonContentExtractor  # noqa: F401
from .py_dispatch import PyExtractor  # noqa: F401

__all__ = ["VocabularyExtractor", "VocabResult", "JsonContentExtractor", "PyExtractor"]
