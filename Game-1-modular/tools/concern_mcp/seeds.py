"""Curated seed edges -- the hand-known cross-vocabulary drift twins (§2, §5).

These are the divergent value pairs the design doc calls out: the same *concept* wearing
two different strings across taxonomies or between authority and usage. Exact-string
indexing can't auto-link them (that's the deliberate no-embeddings trade), so we seed them
so `concept_blast_radius('frost')` also pulls its twin `ice`, and a retire-the-drift change
doesn't under-report.

DriftDetector (Phase 3) additionally flags *un-catalogued* candidates automatically; this
module is the curated backbone it augments.
"""

from __future__ import annotations

from typing import List, Tuple

from .store import ConceptStore

# (value_a, value_b, note) -- order-independent; applied both directions.
DRIFT_TWINS: List[Tuple[str, str, str]] = [
    ("single_target", "single", "authority uses 'single_target'; content/code often say 'single'"),
    ("frost", "ice", "combat damage_type 'frost' vs WMS/element 'ice' -- same concept, different string"),
    ("poison_status", "poison", "status_debuff 'poison_status' vs damage_type 'poison'"),
    ("chill", "slow", "status_debuff near-twins (movement-impair)"),
    ("stun", "root", "status_debuff near-twins (action/movement lock)"),
    ("teleport", "blink", "special 'teleport' with alias-drift 'blink'/'warp'"),
    ("empower", "fortify", "status_buff near-twins (offense vs defense boost)"),
]


def apply_seed_edges(store: ConceptStore) -> int:
    """Add drifts_from edges between known twin values that both exist as concepts.

    Idempotent-ish: callers run this only in a full build (edges are wiped first).
    Returns the number of edges added.
    """
    added = 0
    for a, b, note in DRIFT_TWINS:
        ids_a = _real_ids(store, a)
        ids_b = _real_ids(store, b)
        if not ids_a or not ids_b:
            continue
        # link the primary concept of each (prefer combat_effect, then wms)
        ca, cb = ids_a[0], ids_b[0]
        if ca == cb:
            continue
        store.add_edge(ca, cb, "drifts_from", note)
        store.add_edge(cb, ca, "drifts_from", note)
        added += 2
    store.commit()
    return added


def _real_ids(store: ConceptStore, value: str) -> List[str]:
    """Concept ids for a value, real taxonomies first (combat_effect, wms), skip undefined."""
    rows = store.find_concepts_by_value(value)
    order = {"combat_effect": 0, "wms": 1, "wns": 2}
    rows = [r for r in rows if r["taxonomy"] != "undefined"]
    rows.sort(key=lambda r: order.get(r["taxonomy"], 9))
    return [r["id"] for r in rows]
