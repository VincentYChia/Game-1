"""
Playtest scenario 8: the temp/test world guarantees a village + NPCs near
spawn.

Real villages are scattered 40+ chunks (640+ tiles) from the (0,0) spawn, so
before this feature a tester had to walk a very long way to reach any NPC and
exercise dialogue / quests / factions. The temp world now injects one village
at a fixed near-spawn location whose NPCs are drawn from the real generation
templates — existence guaranteed, identities generation-driven.
"""
import math

import pytest

SPAWN = (0.0, 0.0)
NEAR = 60.0  # tiles — generous bound; the injected village sits ~20 east


def _dist(npc):
    return math.hypot(npc.position.x - SPAWN[0], npc.position.y - SPAWN[1])


def test_test_village_exists_in_world(engine):
    villages = getattr(engine.world, "_villages", [])
    test_village = next(
        (v for v in villages if v.get("locality_id") == 999_999), None)
    assert test_village is not None, (
        "Temp world did not inject the guaranteed near-spawn test village"
    )
    # Its center chunk must actually be near spawn (chunk (1,0) by default).
    cx, cy = test_village["center_chunk"]
    assert abs(cx) <= 3 and abs(cy) <= 3, (
        f"Test village center chunk {test_village['center_chunk']} is not near spawn"
    )
    # NPCs must exist (a few), and be template-driven — one template per NPC.
    assert len(test_village["npc_positions"]) >= 2
    assert len(test_village["npc_templates"]) == len(test_village["npc_positions"])


def _village_npcs(engine):
    """Test-village NPCs, identified by the sentinel locality id in their
    npc_id. Robust to live-position mutation by other session-scoped tests
    (e.g. test_04 relocates every NPC), which plain distance filtering is not.
    """
    return [n for n in engine.npcs
            if "_999999_" in getattr(n.npc_def, "npc_id", "")]


def test_npcs_exist_near_spawn(engine):
    village = next(
        (v for v in engine.world._villages if v.get("locality_id") == 999_999),
        None)
    assert village is not None

    # The village DECLARED its NPC positions near spawn (immutable village data).
    for (nx, ny) in village["npc_positions"]:
        assert math.hypot(nx, ny) <= NEAR, (
            f"Declared NPC position ({nx},{ny}) is not near the (0,0) spawn"
        )

    # And those NPCs were instantiated into engine.npcs.
    npcs = _village_npcs(engine)
    assert len(npcs) >= 2, (
        "Test-village NPCs were not instantiated into engine.npcs"
    )
    for n in npcs:
        assert n.npc_def.name
        assert n.npc_def.interaction_radius > 0


def test_near_spawn_npc_is_interactable(play):
    """A village NPC is interactable: standing on it and pressing F opens
    dialogue with text.

    Relocates the target NPC to a unique tile for the duration of the check so
    the F-handler unambiguously resolves to it (other session-scoped tests pile
    NPCs together, which would make 'player-on-NPC' match a co-located one).
    """
    eng = play.engine
    npcs = _village_npcs(eng)
    if not npcs:
        pytest.skip("no test-village NPC (covered by test_npcs_exist_near_spawn)")
    target = npcs[0]

    UNIQUE = (5.0, 5.0)  # clear of stations (north), chest (3,-2), and NPC piles
    orig_player = (eng.character.position.x, eng.character.position.y)
    orig_npc = (target.position.x, target.position.y)
    try:
        target.position.x, target.position.y = UNIQUE
        eng.character.position.x, eng.character.position.y = UNIQUE
        eng.npc_dialogue_open = False
        eng.active_npc = None

        eng.handle_npc_interaction()
        assert eng.npc_dialogue_open is True, "F did not open dialogue with the NPC"
        assert eng.active_npc is target
        assert eng.npc_dialogue_lines and eng.npc_dialogue_lines[0], (
            "Dialogue opened with no text"
        )
        # Close cleanly.
        eng.handle_npc_interaction()
        assert eng.npc_dialogue_open is False
    finally:
        target.position.x, target.position.y = orig_npc
        eng.character.position.x, eng.character.position.y = orig_player
        eng.npc_dialogue_open = False
        eng.active_npc = None
        play.settle()
