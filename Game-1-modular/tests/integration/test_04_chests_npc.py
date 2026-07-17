"""
Playtest scenario 4: storage-chest transfers and NPC interaction.

Chest transfers pin the 2026-06-10 bounds hardening: out-of-range and
NEGATIVE indices must be no-ops — Python negative indexing previously
made them silently move/pop the WRONG item.

NPC interaction drives the real F-key handler, including the async LLM
dialogue dispatch added 2026-06-10 (speechbank line must appear
instantly regardless of backend availability).
"""
import pytest


# ── Spawn storage chest ──────────────────────────────────────────────

def _slot_index_of(engine, item_id):
    for idx, slot in enumerate(engine.character.inventory.slots):
        if slot and slot.item_id == item_id:
            return idx
    return None


def test_chest_store_and_retrieve_round_trip(play):
    eng = play.engine
    chest = eng.world.spawn_storage_chest
    if chest is None:
        pytest.skip("Temp world has no spawn storage chest")

    play.give('oak_log', 3)
    idx = _slot_index_of(eng, 'oak_log')
    assert idx is not None

    count_before = play.count('oak_log')
    assert eng._transfer_to_spawn_chest(idx) is True
    assert play.count('oak_log') < count_before, "Item not removed from inventory"
    assert any(item_id == 'oak_log' for item_id, _ in chest.contents)

    chest_idx = next(i for i, (item_id, _) in enumerate(chest.contents)
                     if item_id == 'oak_log')
    assert eng._transfer_from_spawn_chest(chest_idx) is True
    assert play.count('oak_log') == count_before, "Item did not come back"


def test_chest_rejects_out_of_range_indices(play):
    eng = play.engine
    chest = eng.world.spawn_storage_chest
    if chest is None:
        pytest.skip("Temp world has no spawn storage chest")

    inventory_snapshot = [
        (s.item_id, s.quantity) if s else None
        for s in eng.character.inventory.slots
    ]
    chest_snapshot = list(chest.contents)

    # Negative and oversized indices must all be no-ops returning False.
    assert eng._transfer_to_spawn_chest(-1) is False
    assert eng._transfer_to_spawn_chest(10_000) is False
    assert eng._transfer_from_spawn_chest(-1) is False
    assert eng._transfer_from_spawn_chest(10_000) is False

    assert inventory_snapshot == [
        (s.item_id, s.quantity) if s else None
        for s in eng.character.inventory.slots
    ], "Invalid index mutated the inventory"
    assert chest_snapshot == list(chest.contents), \
        "Invalid index mutated the chest"


# ── NPC interaction (real F-key path) ────────────────────────────────

def test_npc_dialogue_opens_instantly_and_closes(play):
    eng = play.engine
    if not eng.npcs:
        pytest.skip("No NPCs spawned in this world")

    npc = eng.npcs[0]
    # Walk the NPC to the player (an NPC position is mutable world state).
    npc.position.x = eng.character.position.x + 1
    npc.position.y = eng.character.position.y

    eng.handle_npc_interaction()
    assert eng.npc_dialogue_open is True
    assert eng.active_npc is npc
    # The deterministic speechbank line must be visible IMMEDIATELY —
    # the LLM upgrade (if any backend exists) arrives async later.
    assert eng.npc_dialogue_lines and eng.npc_dialogue_lines[0], \
        "Dialogue panel opened with no text"

    # A few frames must not crash the async dialogue poll.
    play.tick(10)

    eng.handle_npc_interaction()  # second press closes
    assert eng.npc_dialogue_open is False
    assert eng.active_npc is None


def test_npc_interaction_with_no_one_nearby(play):
    eng = play.engine
    # Park every NPC far away.
    for npc in eng.npcs:
        npc.position.x = eng.character.position.x + 500
        npc.position.y = eng.character.position.y + 500

    eng.handle_npc_interaction()
    assert eng.npc_dialogue_open is False, \
        "Dialogue must not open with no NPC in range"
