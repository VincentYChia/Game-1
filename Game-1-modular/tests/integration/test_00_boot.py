"""
Playtest scenario 0: boot the real game headless and live in it.

If this file fails, every other integration scenario is meaningless —
it proves the full GameEngine (databases, world gen, combat, renderer)
boots and survives sustained frame advancement exactly as a player
session does.
"""


def test_engine_booted_with_real_databases(engine):
    from data.databases.material_db import MaterialDatabase
    from data.databases.recipe_db import RecipeDatabase
    from data.databases.skill_db import SkillDatabase

    assert len(MaterialDatabase.get_instance().materials) >= 57
    assert len(RecipeDatabase.get_instance().recipes) >= 150
    assert len(SkillDatabase.get_instance().skills) >= 30


def test_temp_world_entered_with_character(engine):
    assert engine.character is not None
    assert engine.temporary_world is True
    assert engine.start_menu_open is False
    assert engine.character.class_system.current_class is not None


def test_world_has_loaded_chunks_around_player(engine):
    # Temp world generation + update_loaded_chunks must give the player
    # standable terrain.
    assert engine.world is not None
    tile = engine.world.get_tile(engine.character.position)
    assert tile is not None, "Player is standing on a non-generated tile"


def test_enemies_and_training_dummy_spawned(engine):
    enemies = engine.combat_manager.get_all_active_enemies()
    assert len(enemies) >= 1, "Temp world should spawn initial enemies + training dummy"


def test_sustained_play_session_no_crash(play):
    """Two simulated seconds of idle play, rendering every 10th frame.

    Rendering under the dummy driver executes the full Renderer code path
    (UI panels, world draw, notifications) — the place state-dependent
    crashes hide.
    """
    play.tick(frames=120, render_every=10)


def test_movement_through_real_input_pipeline(play):
    """Hold D through the event queue; the character must actually move."""
    x0, y0 = play.position()
    play.move('right', frames=30)
    x1, y1 = play.position()
    assert (x1, y1) != (x0, y0), "30 frames of held D did not move the character"
    # And stopping must actually stop: no residual drift.
    play.settle()
    x2, y2 = play.position()
    play.tick(10)
    assert play.position() == (x2, y2), "Character drifted after key release"
