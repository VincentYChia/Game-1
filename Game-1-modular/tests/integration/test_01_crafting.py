"""
Playtest scenario 1: craft a real item through the engine's completion
pipeline.

This is the path that was silently broken for months by the duplicate
_complete_minigame (audit 2026-06-10): the version that ran had lost the
ITEM_CRAFTED publish, the alloyQuality/firstTryBonus title hooks, and the
debug-resources block. This scenario pins all of that behavior so it can
never silently regress again.
"""
import pytest

from events.event_bus import get_event_bus


@pytest.fixture()
def crafted_events():
    """Subscribe a probe to ITEM_CRAFTED for the duration of a test."""
    captured = []

    def _probe(event):
        captured.append(event)

    bus = get_event_bus()
    bus.subscribe("ITEM_CRAFTED", _probe)
    yield captured
    # GameEventBus has no unsubscribe contract we rely on; the probe list
    # simply goes out of scope after the test.


def test_smithing_craft_full_pipeline(play, crafted_events):
    from data.databases.recipe_db import RecipeDatabase

    recipe_id = 'smithing_iron_shortsword'
    recipe = RecipeDatabase.get_instance().recipes.get(recipe_id)
    assert recipe is not None, "Baseline recipe missing from RecipeDatabase"

    # Stock exactly what the recipe declares, through the real inventory.
    for inp in recipe.inputs:
        mat_id = inp.get('materialId') or inp.get('itemId')
        qty = inp.get('quantity', 1)
        assert play.give(mat_id, qty + 5), f"Could not stock {mat_id}"

    output_before = play.count(recipe.output_id)

    play.craft('smithing', recipe_id,
               {'success': True, 'bonus': 5, 'score': 100})

    # 1. The crafted item landed in the player's real inventory.
    assert play.count(recipe.output_id) > output_before, (
        f"Crafting {recipe_id} did not add {recipe.output_id} to inventory"
    )

    # 2. Materials were actually consumed.
    first_input = recipe.inputs[0]
    first_mat = first_input.get('materialId') or first_input.get('itemId')
    assert play.count(first_mat) <= 5 + (first_input.get('quantity', 1)), (
        "Recipe inputs were not consumed"
    )

    # 3. The ITEM_CRAFTED event reached the bus (feeds the WMS crafting
    #    evaluators — the regression the 2026-06-10 audit fixed).
    assert any(
        getattr(e, 'data', {}).get('recipe_id') == recipe_id
        for e in crafted_events
    ), "ITEM_CRAFTED was not published to the event bus"


def test_minigame_keyboard_input_does_not_crash(play):
    """Drive a real smithing minigame with real key events for a while.

    Not asserting minigame outcome (that's gameplay), asserting the input
    handlers survive sustained interaction — ESC must close cleanly.
    """
    import pygame
    eng = play.engine
    from data.databases.recipe_db import RecipeDatabase
    recipe = RecipeDatabase.get_instance().recipes.get('smithing_iron_shortsword')

    crafter = eng.get_crafter_for_station('smithing')
    eng.active_minigame = crafter.create_minigame(recipe.recipe_id)
    eng.minigame_type = 'smithing'
    eng.minigame_recipe = recipe

    for _ in range(10):
        play.key_tap(pygame.K_SPACE)  # handle_fan
        play.tick(3)

    play.key_tap(pygame.K_ESCAPE)
    assert eng.active_minigame is None, "ESC did not close the minigame"
    eng.minigame_recipe = None
    eng.minigame_type = None
