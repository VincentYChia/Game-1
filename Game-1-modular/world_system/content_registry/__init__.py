"""Content Registry — coordination layer for generator-authored content.

This package implements §7 of
``Development-Plan/WORLD_SYSTEM_WORKING_DOC.md`` (v4): the
single-source-of-truth SQLite store for every piece of content produced
by WES tool mini-stacks, plus the cross-reference graph that keeps the
tool outputs from producing orphans.

The Registry is NOT the runtime database. Runtime databases
(``MaterialDatabase``, ``EnemyDatabase``, etc.) still load from JSON
files at startup. The Registry is:

- **Coordination truth** — staging -> live lifecycle per plan.
- **Cross-reference graph** — ``content_xref`` table wires every
  referenced ID to its definition, so we can block orphan-producing
  commits (§7.3 Pass 1 + Pass 2).
- **Provenance ledger** — every row carries its ``plan_id`` and
  ``source_bundle_id`` so we can walk back from any generated content
  to the WNS bundle that motivated it (``lineage()`` API).

On commit, the Registry ALSO writes the staged content to generated
JSON files (``<tool>-generated-<timestamp>.JSON``) into the sacred
subdirectories so existing databases reload cleanly. This is the
v4 Q4 resolution ("both registry and files"). Sacred content JSONs
authored by designers are NEVER mutated — the generator-authored files
are new sibling files alongside them.

Public API surface (the contract consumed by WES tiers):

- :class:`ContentRegistry` — singleton facade (see
  :mod:`~world_system.content_registry.content_registry`).
- :func:`validate_against_registry` — Pass 1 orphan detection
  during tool parsing (see
  :mod:`~world_system.content_registry.orphan_detector`).
- :func:`check_within_tier_range` — BalanceValidator stub for
  tier-relative numeric sanity checks (see
  :mod:`~world_system.content_registry.balance_validator_stub`).

See ``Development-Plan/PLACEHOLDER_LEDGER.md`` §9, §10, §17 for the
list of placeholders that live in this package.
"""

from world_system.content_registry.content_registry import ContentRegistry
from world_system.content_registry.orphan_detector import (
    validate_against_registry,
)
from world_system.content_registry.balance_validator_stub import (
    check_within_tier_range,
)

__all__ = [
    "ContentRegistry",
    "validate_against_registry",
    "check_within_tier_range",
]
