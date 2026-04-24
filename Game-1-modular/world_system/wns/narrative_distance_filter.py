"""Narrative Distance Filter — §8.8 shallow-going-outward.

Per the working doc, higher-layer prompts should carry **full detail at
the firing layer and its immediate parent**, **brief summaries at higher
parent layers**, and **nothing from sibling addresses** (unless they
share a thread — thread-linked filtering is a future refinement).

Rules live in ``narrative-config.json`` under ``distance_filter``; this
module applies them deterministically on the Python side before any
prompt assembly.

Placeholder alert: word/token budgets per depth are TBD in playtest.
Right now "brief summary" is implemented as "include, but caller should
truncate". See PLACEHOLDER_LEDGER.md §15.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from world_system.wns.narrative_store import NarrativeRow


# Placeholder defaults used when config missing. See PLACEHOLDER_LEDGER.md §15.
_DEFAULT_RULES: Dict[int, Dict[str, List[int]]] = {
    2: {"full_detail_layers": [2, 1], "brief_summary_layers": [3, 4, 5, 6, 7]},
    3: {"full_detail_layers": [3, 2], "brief_summary_layers": [4, 5, 6, 7]},
    4: {"full_detail_layers": [4, 3], "brief_summary_layers": [5, 6, 7]},
    5: {"full_detail_layers": [5, 4], "brief_summary_layers": [6, 7]},
    6: {"full_detail_layers": [6, 5], "brief_summary_layers": [7]},
    7: {"full_detail_layers": [7, 6, 5], "brief_summary_layers": []},
}


@dataclass
class FilteredNarrative:
    """Result of filtering — separates full-detail from brief-summary rows
    so prompt assembly can format each group differently (e.g. 1-2 sentence
    brief for summaries vs. full narrative for detail)."""

    full_detail: List[NarrativeRow] = field(default_factory=list)
    brief_summary: List[NarrativeRow] = field(default_factory=list)

    def all(self) -> List[NarrativeRow]:
        return list(self.full_detail) + list(self.brief_summary)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_detail": [r.to_dict() for r in self.full_detail],
            "brief_summary": [r.to_dict() for r in self.brief_summary],
        }


class NarrativeDistanceFilter:
    """Apply shallow-going-outward rules + sibling-address rejection."""

    def __init__(self, rules: Optional[Dict[int, Dict[str, List[int]]]] = None) -> None:
        self._rules: Dict[int, Dict[str, List[int]]] = (
            {int(k): v for k, v in rules.items()} if rules else dict(_DEFAULT_RULES)
        )
        self._source_path: Optional[str] = None

    # ── Config ───────────────────────────────────────────────────────

    def load_config(self, config_path: str) -> None:
        """Load ``distance_filter`` rules from ``narrative-config.json``."""
        if not os.path.exists(config_path):
            self._source_path = None
            return
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = data.get("distance_filter", {})
        loaded: Dict[int, Dict[str, List[int]]] = {}
        for key, cfg in df.items():
            if not isinstance(cfg, dict):
                continue
            if not key.startswith("nl"):
                continue
            try:
                layer = int(key[2:])
            except ValueError:
                continue
            loaded[layer] = {
                "full_detail_layers": list(cfg.get("full_detail_layers", [])),
                "brief_summary_layers": list(cfg.get("brief_summary_layers", [])),
            }
        if loaded:
            self._rules.update(loaded)
        self._source_path = config_path

    # ── Core filtering ───────────────────────────────────────────────

    def filter_for_firing(
        self,
        layer: int,
        address: str,
        all_narratives: Iterable[NarrativeRow],
    ) -> FilteredNarrative:
        """Given all candidate narratives, keep only the ones this firing
        should see.

        - **Drop sibling addresses** at the firing layer and below. A
          sibling is a row whose ``address`` differs from ``address``
          but is at a layer ≤ firing layer. (Parent addresses at higher
          layers are kept — that's the point of parent_summaries.)
        - **Full-detail layers** for this firing: include rows whose
          layer is in ``full_detail_layers``.
        - **Brief-summary layers**: include rows whose layer is in
          ``brief_summary_layers``. Brevity is the caller's job
          (placeholder: we include them; caller truncates).

        This is conservative: rows not classified under either rule are
        dropped entirely (e.g. a stray row at a layer neither listed as
        full-detail nor brief-summary).
        """
        rule = self._rules.get(int(layer), _DEFAULT_RULES.get(int(layer), {}))
        full_set = set(rule.get("full_detail_layers", []))
        brief_set = set(rule.get("brief_summary_layers", []))

        full_detail: List[NarrativeRow] = []
        brief_summary: List[NarrativeRow] = []

        for row in all_narratives:
            # Sibling address rejection at firing layer and below.
            if row.layer <= layer and row.address != address:
                continue
            if row.layer in full_set:
                full_detail.append(row)
            elif row.layer in brief_set:
                brief_summary.append(row)
            # Else: outside window — drop.

        return FilteredNarrative(
            full_detail=full_detail,
            brief_summary=brief_summary,
        )

    # ── Debug ────────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "source_path": self._source_path,
            "rules_for_layers": sorted(self._rules.keys()),
        }
