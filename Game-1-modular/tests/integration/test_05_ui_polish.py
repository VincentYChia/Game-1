"""
Playtest scenario 5: UI polish behaviors (2026-06-10 Track A).

Pins:
1. Menu mutual exclusivity — one overlay panel at a time, driven through
   the real keyboard pipeline (C/E/K/M/J).
2. Inventory hit-test geometry — engine hover/click math and renderer
   drawing must share Config's single source (the drifted copy made
   Q-drop target the slot ABOVE the hovered one).
"""
import pygame

from core.config import Config


def _close_all_panels(play):
    eng = play.engine
    char = eng.character
    if char.stats_ui_open:
        char.toggle_stats_ui()
    if char.equipment_ui_open:
        char.toggle_equipment_ui()
    if char.skills_ui_open:
        char.toggle_skills_ui()
    if char.encyclopedia.is_open:
        char.encyclopedia.toggle()
    if eng.map_system.map_open:
        eng.map_system.close_map()
    eng.quest_log_open = False
    play.settle()


def test_opening_one_menu_closes_the_others(play):
    eng = play.engine
    char = eng.character
    _close_all_panels(play)

    play.key_tap(pygame.K_c)            # stats
    assert char.stats_ui_open is True

    play.key_tap(pygame.K_e)            # equipment must close stats
    assert char.equipment_ui_open is True
    assert char.stats_ui_open is False, "Stats stayed open under equipment"

    play.key_tap(pygame.K_m)            # map must close equipment
    assert eng.map_system.map_open is True
    assert char.equipment_ui_open is False, "Equipment stayed open under map"

    play.key_tap(pygame.K_j)            # quest log must close map
    assert eng.quest_log_open is True
    assert eng.map_system.map_open is False, "Map stayed open under quest log"

    play.key_tap(pygame.K_k)            # skills must close quest log
    assert char.skills_ui_open is True
    assert eng.quest_log_open is False, "Quest log stayed open under skills"

    _close_all_panels(play)


def test_menu_toggle_still_closes_itself(play):
    """Exclusivity must not break plain toggle-to-close."""
    eng = play.engine
    char = eng.character
    _close_all_panels(play)

    play.key_tap(pygame.K_c)
    assert char.stats_ui_open is True
    play.key_tap(pygame.K_c)
    assert char.stats_ui_open is False
    # And nothing else got opened as a side effect.
    assert not char.equipment_ui_open and not char.skills_ui_open
    assert not eng.map_system.map_open and not eng.quest_log_open


def test_hover_geometry_matches_single_source(play):
    """_get_hovered_inventory_slot must resolve the slot whose drawn rect
    the cursor is inside — computed from the same Config single source the
    renderer uses. Before the fix this function was offset 20px vertically
    (Q-drop hit the wrong slot)."""
    eng = play.engine
    start_x, start_y = Config.inventory_grid_origin()
    slot = Config.INVENTORY_SLOT_SIZE
    spacing = Config.INVENTORY_SLOT_SPACING
    per_row = Config.INVENTORY_SLOTS_PER_ROW

    # Dead-center of slot 0 and of slot (row 1, col 2).
    cases = [
        (0, (start_x + slot // 2, start_y + slot // 2)),
        (per_row + 2, (start_x + 2 * (slot + spacing) + slot // 2,
                       start_y + (slot + spacing) + slot // 2)),
    ]
    for expected_idx, pos in cases:
        eng.mouse_pos = pos
        got = eng._get_hovered_inventory_slot()
        assert got == expected_idx, (
            f"Hover at drawn center of slot {expected_idx} resolved to "
            f"{got} — engine hit-test has drifted from renderer geometry"
        )

    # A point in the spacing gutter between slots resolves to nothing.
    eng.mouse_pos = (start_x + slot + spacing // 2, start_y + slot // 2)
    assert eng._get_hovered_inventory_slot() == -1


def test_npc_spatial_index_is_complete_and_renders(play):
    """The chunk-bucket index over engine.npcs must account for every NPC
    (12,301 village NPCs made render_npcs an O(N)-per-frame sweep), and
    rendered frames must keep working through the bucketed path."""
    eng = play.engine
    renderer = eng.renderer

    buckets = renderer._get_npc_chunk_buckets(eng.npcs)
    assert sum(len(v) for v in buckets.values()) == len(eng.npcs), (
        "Spatial index lost NPCs — bucketed rendering would hide them"
    )

    # Same list object + length -> the cached index is reused, not rebuilt.
    assert renderer._get_npc_chunk_buckets(eng.npcs) is buckets

    # Full render frames through the bucketed path.
    play.tick(10, render_every=1)
