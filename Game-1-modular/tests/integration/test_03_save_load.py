"""
Playtest scenario 3: save/load round-trip + crash-corruption recovery.

Exercises the REAL SaveManager against the real engine state — the same
call the pause menu's Save & Exit makes — including the 2026-06-10
hardening: atomic writes, .bak backup, and corrupt-save recovery.
"""
import json
import os

from core.paths import get_save_path

SAVE_NAME = 'integration_test_save.json'


def test_save_writes_loadable_state(play):
    eng = play.engine
    assert play.save(SAVE_NAME) is True

    path = get_save_path(SAVE_NAME)
    assert os.path.exists(path), "Save file was not written"
    # No stray temp file may survive an atomic write.
    assert not os.path.exists(str(path) + '.tmp'), "Atomic temp file leaked"

    data = play.load_raw(SAVE_NAME)
    assert data is not None, "Fresh save failed to load"

    # Round-trip integrity on player-critical fields. The serializer's
    # top-level key is "player" (save_manager.create_save_data).
    char = data.get('player', {})
    assert char, "Save has no player section"
    saved_pos = char.get('position')
    assert saved_pos is not None, "Save lost the character position"
    saved_x = saved_pos.get('x') if isinstance(saved_pos, dict) else saved_pos[0]
    assert abs(saved_x - eng.character.position.x) < 0.01, (
        f"Saved x={saved_x} != live x={eng.character.position.x}"
    )


def test_second_save_keeps_backup_of_first(play):
    assert play.save(SAVE_NAME) is True
    assert play.save(SAVE_NAME) is True
    backup = str(get_save_path(SAVE_NAME)) + '.bak'
    assert os.path.exists(backup), (
        "Second save did not preserve the previous save as .bak"
    )
    with open(backup, encoding='utf-8') as f:
        assert json.load(f).get('version'), ".bak is not a valid save"


def test_corrupt_save_recovers_from_backup(play):
    # Two saves: a good .bak and a primary we then corrupt — simulating
    # the historical crash-mid-write failure mode.
    assert play.save(SAVE_NAME) is True
    assert play.save(SAVE_NAME) is True
    path = get_save_path(SAVE_NAME)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('{"version": "3.0", "character": {TRUNCATED')

    data = play.load_raw(SAVE_NAME)
    assert data is not None, (
        "Corrupt primary save must fall back to .bak, not lose the session"
    )
    assert data.get('version'), "Recovered data is not a structured save"


def test_inventory_survives_round_trip(play):
    eng = play.engine
    marker_item = 'iron_ingot'
    play.give(marker_item, 7)
    count_live = play.count(marker_item)

    assert play.save(SAVE_NAME) is True
    data = play.load_raw(SAVE_NAME)

    # Serialized inventory must contain the marker at the live quantity.
    inv = data.get('player', {}).get('inventory', [])
    saved_qty = 0
    stacks = inv.get('slots', inv) if isinstance(inv, dict) else inv
    for stack in stacks:
        if isinstance(stack, dict) and stack.get('item_id') == marker_item:
            saved_qty += stack.get('quantity', 0)
    assert saved_qty == count_live, (
        f"Round-trip lost inventory: live {count_live}x {marker_item}, "
        f"saved {saved_qty}x"
    )
