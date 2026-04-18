# Faction System — Implementation Status

**Date**: April 18, 2026  
**Phase**: Phase 2 Complete  
**Status**: Ready for Phase 3 Integration

---

## Summary

The faction system is a **recording and retrieval system parallel to WMS**, not a behavior simulator. It tracks:
- Player affinity with factions (-100 to 100)
- NPC affinity with factions (-100 to 100)
- NPC personal opinion of player (-100 to 100)
- Location cultural attitudes (-100 to 100)
- NPC belonging to factions (0-1 significance)

All data is stored sparsely (only non-zero values) in SQLite, with hierarchical inheritance for location defaults.

---

## Phase 2 Completion

### What's Complete

**Database** (schema.py)
- ✅ 8 tables with proper constraints and indexes
- ✅ Sparse storage (only non-zero values)
- ✅ Hierarchical location affinity with summing
- ✅ Bootstrap data for initial affinity defaults

**Data Models** (models.py)
- ✅ FactionTag (tag + significance 0-1 + role + narrative hooks)
- ✅ NPCProfile (narrative + belonging_tags + npc_affinity)
- ✅ PlayerProfile (player affinity with tags)
- ✅ LocationAffinityDefault (-100 to 100 cultural baseline)
- ✅ NPCAffinityTowardPlayer (per-NPC personal opinion)

**Manager** (faction_system.py)
- ✅ 17 methods covering all CRUD operations
- ✅ NPC profile management (add, retrieve, update tags)
- ✅ Player affinity operations (set, adjust, get, get all)
- ✅ NPC affinity toward tags (set, get)
- ✅ NPC affinity toward player (set, adjust, get)
- ✅ Location affinity defaults (get, compute with inheritance)
- ✅ Save/restore for game state persistence

**Testing** (test_faction_phase2plus.py)
- ✅ 4 test classes with 11 test methods
- ✅ NPC profile CRUD
- ✅ Player affinity operations
- ✅ Location inheritance
- ✅ Integration workflow

**Documentation** (NEW)
- ✅ PHASE_2_ARCHITECTURE.md — High-level design
- ✅ INFORMATION_FLOW.md — Clear data flow explanation
- ✅ LLM_INTEGRATION.md — Prompts, payloads, integration patterns

### What's Removed

- ✅ ReputationRulesEngine (no longer needed; quest system provides deltas directly)
- ✅ Reputation rules test cases (replaced with simpler quest delta simulation)

### What's Ready for Integration

All components are in place to:
1. **Record affinity changes** from game events (quests, combat, trades)
2. **Retrieve context** for NPC dialogue generation
3. **Pass data to LLM** via BackendManager for dialogue
4. **Feed events to WMS** Layer 2 evaluator for consolidation

---

## Phase 3 Integration Points

### Quest System Integration

**What needs to happen**:
```python
# In quest system, when quest completes:
deltas = quest.get_affinity_deltas()  # Provides estimates
for tag, delta in deltas.items():
    faction_sys.adjust_player_affinity(player_id, tag, delta)
# GameEventBus automatically publishes FACTION_REP_CHANGED
```

**Status**: Not yet implemented (external to faction system)

### NPC Agent Integration

**What needs to happen**:
```python
# In NPC dialogue generation:
context = {
    "npc": faction_sys.get_npc_profile(npc_id),
    "player_affinity": faction_sys.get_all_player_affinities(player_id),
    "npc_opinion": faction_sys.get_npc_affinity_toward_player(npc_id),
    "location": faction_sys.compute_inherited_affinity(hierarchy)
}

backend = BackendManager.get_instance()
dialogue = backend.generate_dialogue(
    system_prompt="...",
    user_prompt=format_context(context),
    temperature=0.7
)
```

**Status**: Not yet implemented (external to faction system)

### WMS Consolidation Integration

**What happens**:
1. adjust_player_affinity() publishes FACTION_REP_CHANGED event
2. WMS FactionReputationEvaluator listens
3. Evaluator produces InterpretedEvent with faction tags
4. Event feeds into Layer 3+ consolidation pipeline

**Status**: Event publishing ready; WMS evaluator integration pending

---

## Data Flow Summary

### Recording Direction
```
Game Event
  ↓
Quest/Combat System provides delta estimate
  ↓
FactionSystem.adjust_player_affinity()
  ↓
Database updated (sparse)
  ↓
FACTION_REP_CHANGED event published
  ↓
WMS consolidation pipeline
```

### Retrieval Direction
```
NPC dialogue request
  ↓
NPC Agent gathers context (4 faction system calls)
  ↓
BackendManager.generate_dialogue()
  ↓
Dialogue returned to game
```

---

## Key Design Decisions

1. **No Rules Engine**: Quest system directly provides deltas
2. **Sparse Storage**: Only non-zero values
3. **Hierarchical Defaults**: Location affinity cascades with summing
4. **Separate Opinion Tracks**: Player affinity, NPC affinity, NPC opinion
5. **Event-Driven**: All changes publish events for WMS
6. **LLM Integration**: Via BackendManager (Ollama, Claude, Mock)

---

## Next Steps (Phase 3)

**Highest Priority**:
1. Implement NPC dialogue integration
2. Wire FactionSystem context gathering
3. Test with BackendManager and LLM

**High Priority**:
4. Implement quest system affinity provision
5. Verify WMS event integration
6. Test end-to-end: quest → affinity → narrative

---

## References

- **INFORMATION_FLOW.md** — Data flow explanation
- **LLM_INTEGRATION.md** — Prompts and integration patterns
- **PHASE_2_ARCHITECTURE.md** — Design principles
