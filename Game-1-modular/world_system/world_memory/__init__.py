"""World Memory System — the information state layer for the Living World.

Seven-layer architecture:
  Layer 0: GameEventBus (ephemeral pub/sub) — existing
  Layer 1: Numerical stats (StatTracker, cumulative counters) — existing
  Raw Event Pipeline: Structured event records from bus — SQLite (infrastructure, not a numbered layer)
  Layer 2: Simple text events (evaluator-generated narrative descriptions) — SQLite
  Layer 3: Municipality/local consolidation (per-locality summaries) — in-memory + SQLite
  Layer 4: Smaller region events (district/province summaries) — in-memory + SQLite
  Layer 5: Larger region/country events (realm state) — in-memory + SQLite
  Layer 6: Intercountry/world events (world narrative and threads) — in-memory + SQLite
"""
