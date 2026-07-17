"""
2026-07 review Batch 1 — progression + crafting-failure correctness.

1. EXP cascades: a single large grant resolves ALL crossed level-ups in the
   same call (previously one per call; surplus banked and resolved on the
   next grant of any size — no EXP lost, but phantom late level-ups).
2. Minigame-failure material loss is tier-scaled (30-90% via the crafter's
   declared loss_fraction), not 100%: the crafter's partial deduction hit a
   throwaway dict copy while the engine consumed the full recipe.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from entities.components.leveling import LevelingSystem  # noqa: E402


# ── EXP cascade ──────────────────────────────────────────────────────

def test_multi_level_grant_cascades_in_one_call():
    lv = LevelingSystem()
    # L1->L2 needs 350 (200*1.75), L2->L3 needs 612 — grant enough for both.
    grant = lv.exp_requirements[2] + lv.exp_requirements[3] + 10
    assert lv.add_exp(grant) is True
    assert lv.level == 3, f"expected cascade to level 3, got {lv.level}"
    assert lv.unallocated_stat_points == 2
    assert 0 <= lv.current_exp < lv.get_exp_for_next_level()


def test_exp_is_never_lost_across_grants():
    a, b = LevelingSystem(), LevelingSystem()
    total = a.exp_requirements[2] + a.exp_requirements[3] + 57
    a.add_exp(total)                      # one big grant
    for _ in range(10):                   # same total, dribbled
        b.add_exp(total // 10)
    b.add_exp(total - (total // 10) * 10)
    assert a.level == b.level
    assert a.current_exp == b.current_exp


def test_max_level_cap_holds():
    lv = LevelingSystem()
    # The curve compounds hard: L30 needs ~2.3e9 cumulative. Grant the
    # exact curve total plus slack and confirm the cap holds.
    total_curve = sum(lv.exp_requirements[lvl] for lvl in range(2, lv.max_level + 1))
    lv.add_exp(total_curve + 1000)
    assert lv.level == lv.max_level
    assert lv.add_exp(100) is False


# ── partial failure consumption ──────────────────────────────────────

class _Slot:
    def __init__(self, item_id, quantity):
        self.item_id = item_id
        self.quantity = quantity


class _Inv:
    def __init__(self, items):
        self.slots = [_Slot(i, q) for i, q in items.items()]

    def count(self, item_id):
        return sum(s.quantity for s in self.slots if s and s.item_id == item_id)


class _Recipe:
    recipe_id = "test_recipe"

    def __init__(self, inputs):
        self.inputs = inputs


def _db():
    from data.databases.recipe_db import RecipeDatabase
    return RecipeDatabase.get_instance()


def test_partial_consume_takes_declared_fraction():
    inv = _Inv({"iron_ingot": 10, "oak_plank": 4})
    recipe = _Recipe([{"materialId": "iron_ingot", "quantity": 10},
                      {"materialId": "oak_plank", "quantity": 4}])
    consumed = _db().consume_materials_partial(recipe, inv, 0.5)
    assert consumed == {"iron_ingot": 5, "oak_plank": 2}
    assert inv.count("iron_ingot") == 5
    assert inv.count("oak_plank") == 2


def test_partial_consume_fraction_bounds():
    inv = _Inv({"iron_ingot": 10})
    recipe = _Recipe([{"materialId": "iron_ingot", "quantity": 10}])
    assert _db().consume_materials_partial(recipe, inv, 0.0) == {}
    assert inv.count("iron_ingot") == 10
    _db().consume_materials_partial(recipe, inv, 5.0)  # clamps to 1.0
    assert inv.count("iron_ingot") == 0


def test_partial_consume_best_effort_when_short():
    inv = _Inv({"iron_ingot": 3})
    recipe = _Recipe([{"materialId": "iron_ingot", "quantity": 10}])
    consumed = _db().consume_materials_partial(recipe, inv, 0.9)  # wants 9
    assert consumed == {"iron_ingot": 3}
    assert inv.count("iron_ingot") == 0
