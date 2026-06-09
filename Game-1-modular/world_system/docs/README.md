# World System Documentation

## Start Here

| Document | Purpose |
|----------|---------|
| **[../../../Development-Plan/SYSTEMS_CATALOG.md](../../../Development-Plan/SYSTEMS_CATALOG.md)** | **Single baseline catalog** — every system in the game with status (WORKING / PARTIAL / DESIGNED-NOT-WIRED). Start here for "is X working?" questions. |
| **[../../../Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md](../../../Development-Plan/WMS_WNS_LAYER_CORRESPONDENCE.md)** | **2026-06-05 canonical** for the WMS↔WNS layer-flow design (Model C: cascade baseline + WMS-firing peak + NL1 dialogue → L3 feed). Read before touching any layer-flow code. |
| **[HANDOFF_STATUS.md](HANDOFF_STATUS.md)** | Current implementation state — what's built, what's next, how to continue |
| **[WORLD_MEMORY_SYSTEM.md](WORLD_MEMORY_SYSTEM.md)** | Design document for the 7-layer data architecture. Also describes consumer systems (§12) for reference, but is NOT the source of truth for consumer implementations. §7.4 has a 2026-06-05 staleness flag — Layer 6 is implemented; the "future" qualifier was wrong. |
| **[TAG_LIBRARY.md](TAG_LIBRARY.md)** | 60-category tag taxonomy across 7 layers — the primary indexing/retrieval system |
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
