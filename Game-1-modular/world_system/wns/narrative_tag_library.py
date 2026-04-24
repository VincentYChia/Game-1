"""Narrative Tag Library — WNS-specific tag taxonomy.

Mirrors the ``world_memory/tag_library.py`` pattern but lives in its own
file, loads from its own JSON source (``narrative-tag-definitions.JSON``),
and owns a separate set of address-tag prefixes.

Sibling-system invariant (CC5 in the working doc): WMS and WNS do not
share tag vocabulary. The geographic address prefixes (``world:`` ..
``locality:``) are IMPORTED from WMS's ``geographic_registry`` so narrative
events carrying those tags honor the same immutability contract. On top
of that, WNS adds narrative-specific address prefixes ``thread:``,
``arc:``, ``witness:``.

Placeholder alert: the starter categories come from
``narrative-tag-definitions.JSON``. See
``Development-Plan/PLACEHOLDER_LEDGER.md`` §5 — the designer owns the
real taxonomy; the WNS agent seeded the file so the pipeline compiles.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import (
    Any,
    ClassVar,
    Dict,
    FrozenSet,
    List,
    Optional,
    Tuple,
)

# Geographic address prefixes come from WMS — same rule, reused.
from world_system.world_memory.geographic_registry import (
    ADDRESS_TAG_PREFIXES as _WMS_ADDRESS_TAG_PREFIXES,
)


# ── Narrative-specific address prefixes ───────────────────────────────

# Per §4.2b of the working doc: narrative addresses are facts about the
# narrative event, set at capture, never rewritten by an LLM.
_NARRATIVE_ADDRESS_PREFIXES: Tuple[str, ...] = (
    "thread:",
    "arc:",
    "witness:",
)


# Full prefix list combining geographic + narrative-specific. Order is
# geographic-first (matches WMS), then narrative-specific. Stable order
# matters for deterministic partitioning.
ADDRESS_TAG_PREFIXES: Tuple[str, ...] = tuple(
    list(_WMS_ADDRESS_TAG_PREFIXES) + list(_NARRATIVE_ADDRESS_PREFIXES)
)


def is_narrative_address_tag(tag: str) -> bool:
    """True if the tag is a narrative/geographic address fact (never LLM-rewritable)."""
    return any(tag.startswith(p) for p in ADDRESS_TAG_PREFIXES)


# ── Tag category dataclass ───────────────────────────────────────────

@dataclass(frozen=True)
class NarrativeTagCategory:
    """Definition of a single narrative tag category."""

    category_id: str
    values: FrozenSet[str]
    layer_unlocked: int
    is_dynamic: bool = False
    description: str = ""


# ── Library singleton ────────────────────────────────────────────────

class NarrativeTagLibrary:
    """Loads and serves the narrative tag taxonomy.

    Singleton following the project pattern. Reads
    ``narrative-tag-definitions.JSON`` on first access. All behavior is
    read-only at runtime; new tag categories cannot be added at runtime
    (future-direction per §4.2: narrative-specific tag unlocks are allowed
    over time but happen by editing the JSON, not by runtime mutation).
    """

    _instance: ClassVar[Optional["NarrativeTagLibrary"]] = None

    DEFAULT_CONFIG_FILENAME = "narrative-tag-definitions.JSON"

    def __init__(self) -> None:
        self._categories: Dict[str, NarrativeTagCategory] = {}
        self._address_prefixes: Tuple[str, ...] = ADDRESS_TAG_PREFIXES
        self._loaded: bool = False
        self._source_path: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "NarrativeTagLibrary":
        if cls._instance is None:
            cls._instance = cls()
            # Auto-load from default location on first get.
            try:
                cls._instance.load(cls._default_config_path())
            except FileNotFoundError:
                # Graceful — caller may .load() explicitly with a test path.
                pass
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test helper."""
        cls._instance = None

    @staticmethod
    def _default_config_path() -> str:
        """Default path to ``narrative-tag-definitions.JSON`` relative to
        ``world_system/config/``."""
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(
            os.path.join(
                here, os.pardir, "config",
                NarrativeTagLibrary.DEFAULT_CONFIG_FILENAME,
            )
        )

    # ── Loading ──────────────────────────────────────────────────────

    def load(self, config_path: str) -> int:
        """Load categories from JSON. Returns number of categories loaded."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"NarrativeTagLibrary config not found: {config_path}"
            )
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._categories.clear()
        categories_block: Dict[str, Any] = data.get("categories", {})
        for cat_id, cfg in categories_block.items():
            values = frozenset(cfg.get("values", []))
            self._categories[cat_id] = NarrativeTagCategory(
                category_id=cat_id,
                values=values,
                layer_unlocked=int(cfg.get("layer_unlocked", 2)),
                is_dynamic=bool(cfg.get("is_dynamic", False)),
                description=str(cfg.get("description", "")),
            )

        # Extra address prefixes declared in JSON (should match module-level
        # ADDRESS_TAG_PREFIXES; if they diverge the module-level tuple wins
        # to keep a single source-of-truth for partitioning code).
        self._loaded = True
        self._source_path = config_path
        return len(self._categories)

    # ── Queries ──────────────────────────────────────────────────────

    @property
    def address_prefixes(self) -> Tuple[str, ...]:
        return self._address_prefixes

    def get_category(self, category_id: str) -> Optional[NarrativeTagCategory]:
        return self._categories.get(category_id)

    def get_categories_for_layer(
        self, layer: int
    ) -> Dict[str, NarrativeTagCategory]:
        return {
            k: v for k, v in self._categories.items()
            if v.layer_unlocked <= layer
        }

    def validate_tag(self, tag: str, layer: int) -> bool:
        """Check if a tag string is valid at a given layer.

        Address tags (``thread:``, ``arc:``, ``witness:``, geographic) are
        always valid — they're facts, not content tags.
        """
        if is_narrative_address_tag(tag):
            return True
        if ":" not in tag:
            return False
        category, value = tag.split(":", 1)
        cat_def = self._categories.get(category)
        if cat_def is None:
            return False
        if cat_def.layer_unlocked > layer:
            return False
        if cat_def.is_dynamic:
            return True
        return value in cat_def.values

    def partition_address_and_content(
        self, tags: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Split a tag list into (address_tags, content_tags).

        Mirrors ``world_memory.geographic_registry.partition_address_and_content``
        but recognizes narrative-specific addresses too (``thread:`` etc.).
        """
        address: List[str] = []
        content: List[str] = []
        for t in tags:
            (address if is_narrative_address_tag(t) else content).append(t)
        return address, content

    # ── Stats ────────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "loaded": self._loaded,
            "source_path": self._source_path,
            "total_categories": len(self._categories),
            "dynamic_categories": sum(
                1 for c in self._categories.values() if c.is_dynamic
            ),
            "address_prefixes": list(self._address_prefixes),
        }
