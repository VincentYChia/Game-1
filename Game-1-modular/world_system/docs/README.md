# World System Documentation

## Start Here

| Document | Purpose |
|----------|---------|
| **[HANDOFF_STATUS.md](HANDOFF_STATUS.md)** | Current implementation state — what's built, what's next, how to continue |
| **[WORLD_MEMORY_SYSTEM.md](WORLD_MEMORY_SYSTEM.md)** | Design document for the 7-layer data architecture. Also describes consumer systems (§12) for reference, but is NOT the source of truth for consumer implementations |
| **[FOUNDATION_IMPLEMENTATION_PLAN.md](FOUNDATION_IMPLEMENTATION_PLAN.md)** | Detailed implementation plan for Layer 1-2 infrastructure (mostly executed) |

## Run Tests

```bash
cd Game-1-modular
python world_system/world_memory/test_stat_store.py          # 19 tests — SQL stat storage + dimensional breakdowns
python world_system/world_memory/test_foundation_pipeline.py  # 27 tests — triggers, time envelopes, daily ledgers
python world_system/world_memory/test_memory_system.py        # 10 tests — event store, registries, full pipeline
```

## Archive

The `archive/` directory contains prior separate design documents that were consolidated into `WORLD_MEMORY_SYSTEM.md`. They are retained for historical reference but are **superseded**.
