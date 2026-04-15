"""World Memory System — the information state layer for the Living World.

Seven-layer architecture, aggregation tier per layer:
  Layer 0: GameEventBus (ephemeral pub/sub)
  Layer 1: Numerical stats (StatTracker, cumulative counters)
  Raw Event Pipeline: structured event records (infrastructure)
  Layer 2: Capture — one event per evaluator firing, tagged with the
           full 6-tier address (world/nation/region/province/district/
           locality if present)
  Layer 3: game District aggregation — drops `locality:` tag
  Layer 4: game Province aggregation — drops `district:` tag
  Layer 5: game Region aggregation — drops `province:` tag
  Layer 6: game Nation aggregation — drops `region:` tag (future)
  Layer 7: game World aggregation — drops `nation:` tag (future)

Address tags are FACTS assigned at L2 capture from chunk position.
No layer and no LLM ever synthesizes or rewrites them. See
docs/ARCHITECTURAL_DECISIONS.md.
"""
