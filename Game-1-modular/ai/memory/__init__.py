"""World Memory System — the information state layer for the Living World.

Six-layer architecture:
  Layer 0: GameEventBus (ephemeral pub/sub) — existing
  Layer 1: StatTracker (cumulative counters) — existing
  Layer 2: Raw event records (structured facts) — SQLite
  Layer 3: Interpreted events (narrative descriptions) — SQLite
  Layer 4: Local aggregation (per-locality summaries) — in-memory + SQLite
  Layer 5: Regional aggregation (province/realm summaries) — in-memory + SQLite
"""
